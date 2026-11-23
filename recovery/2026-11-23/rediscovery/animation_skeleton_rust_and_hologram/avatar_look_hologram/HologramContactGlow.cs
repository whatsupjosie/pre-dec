using System.Collections.Generic;
using UnityEngine;
using Unity.Collections;
using Unity.Jobs;

namespace PubCast.Avatars
{
    /// <summary>
    /// Advanced contact glow system for hologram avatars
    /// Handles real-time contact detection and vertex color updates for glow effects
    /// </summary>
    [RequireComponent(typeof(SkinnedMeshRenderer))]
    public class HologramContactGlow : MonoBehaviour
    {
        [Header("Contact Detection Settings")]
        [SerializeField] private float contactRadius = 0.1f;
        [SerializeField] private LayerMask contactLayers = -1;
        [SerializeField] private float glowIntensity = 2.0f;
        [SerializeField] private float glowFadeSpeed = 3.0f;
        [SerializeField] private bool enableAvatarToAvatarOnly = true;
        
        [Header("Performance Settings")]
        [SerializeField] private int maxContactPoints = 10;
        [SerializeField] private float updateFrequency = 60f; // FPS
        [SerializeField] private bool useJobSystem = true;
        
        [Header("Contact Types")]
        [SerializeField] private ContactTypeSettings[] contactTypes = new ContactTypeSettings[]
        {
            new ContactTypeSettings { name = "HandToHand", intensity = 1.0f, radius = 0.08f },
            new ContactTypeSettings { name = "HandToFace", intensity = 0.8f, radius = 0.06f },
            new ContactTypeSettings { name = "FaceToFace", intensity = 1.2f, radius = 0.05f },
            new ContactTypeSettings { name = "BodyToBody", intensity = 0.6f, radius = 0.12f }
        };
        
        [Header("Debug")]
        [SerializeField] private bool showContactGizmos = true;
        [SerializeField] private bool logContactEvents = false;
        
        // Components
        private SkinnedMeshRenderer meshRenderer;
        private Mesh originalMesh;
        private Mesh workingMesh;
        private Transform[] bodyJoints;
        
        // Contact tracking
        private List<ActiveContact> activeContacts = new List<ActiveContact>();
        private Dictionary<string, int> jointNameToIndex = new Dictionary<string, int>();
        private Color[] vertexColors;
        private Vector3[] vertices;
        private bool meshDataDirty = false;
        
        // Performance optimization
        private float lastUpdateTime;
        private float updateInterval;
        private static readonly List<HologramContactGlow> allHolograms = new List<HologramContactGlow>();
        
        // Job system data
        private JobHandle contactJobHandle;
        private NativeArray<ContactCheckData> contactCheckData;
        private NativeArray<ContactResult> contactResults;
        
        #region Structs and Enums
        
        [System.Serializable]
        public class ContactTypeSettings
        {
            public string name;
            public float intensity = 1.0f;
            public float radius = 0.1f;
            public Color glowColor = Color.cyan;
        }
        
        public struct ActiveContact
        {
            public Vector3 worldPosition;
            public int vertexIndex;
            public float intensity;
            public float startTime;
            public string contactType;
            public HologramContactGlow otherAvatar;
        }
        
        public struct ContactCheckData
        {
            public Vector3 position;
            public float radius;
            public int jointIndex;
        }
        
        public struct ContactResult
        {
            public bool hasContact;
            public Vector3 contactPoint;
            public float distance;
            public int otherJointIndex;
        }
        
        #endregion
        
        #region Unity Lifecycle
        
        void Awake()
        {
            meshRenderer = GetComponent<SkinnedMeshRenderer>();
            originalMesh = meshRenderer.sharedMesh;
            
            // Create working copy of mesh for vertex color modifications
            workingMesh = Instantiate(originalMesh);
            meshRenderer.sharedMesh = workingMesh;
            
            // Initialize vertex colors
            InitializeVertexColors();
            
            // Setup update frequency
            updateInterval = 1f / updateFrequency;
            
            // Find body joints for contact detection
            FindBodyJoints();
        }
        
        void OnEnable()
        {
            allHolograms.Add(this);
        }
        
        void OnDisable()
        {
            allHolograms.Remove(this);
            
            if (contactJobHandle.IsCompleted == false)
                contactJobHandle.Complete();
                
            if (contactCheckData.IsCreated)
                contactCheckData.Dispose();
            if (contactResults.IsCreated)
                contactResults.Dispose();
        }
        
        void Update()
        {
            if (Time.time - lastUpdateTime >= updateInterval)
            {
                if (useJobSystem)
                    UpdateContactsWithJobs();
                else
                    UpdateContactsMainThread();
                    
                lastUpdateTime = Time.time;
            }
            
            // Update vertex colors if data has changed
            if (meshDataDirty)
            {
                ApplyVertexColors();
                meshDataDirty = false;
            }
            
            // Fade existing contacts
            FadeContacts();
        }
        
        #endregion
        
        #region Initialization
        
        private void InitializeVertexColors()
        {
            vertices = workingMesh.vertices;
            vertexColors = new Color[vertices.Length];
            
            // Initialize with base hologram color (low intensity blue/cyan)
            Color baseColor = new Color(0f, 0.1f, 0.2f, 1f);
            for (int i = 0; i < vertexColors.Length; i++)
            {
                vertexColors[i] = baseColor;
            }
            
            workingMesh.colors = vertexColors;
        }
        
        private void FindBodyJoints()
        {
            // Find standard humanoid joints for contact detection
            string[] jointNames = {
                "head", "neck", "chest", 
                "left_hand", "right_hand",
                "left_shoulder", "right_shoulder",
                "left_hip", "right_hip",
                "left_foot", "right_foot"
            };
            
            List<Transform> foundJoints = new List<Transform>();
            
            foreach (string jointName in jointNames)
            {
                Transform joint = FindChildRecursive(transform, jointName);
                if (joint != null)
                {
                    foundJoints.Add(joint);
                    jointNameToIndex[jointName] = foundJoints.Count - 1;
                }
                else
                {
                    Debug.LogWarning($"Joint '{jointName}' not found on {gameObject.name}");
                }
            }
            
            bodyJoints = foundJoints.ToArray();
        }
        
        private Transform FindChildRecursive(Transform parent, string name)
        {
            foreach (Transform child in parent)
            {
                if (child.name.ToLower().Contains(name.ToLower()))
                    return child;
                    
                Transform result = FindChildRecursive(child, name);
                if (result != null)
                    return result;
            }
            return null;
        }
        
        #endregion
        
        #region Contact Detection
        
        private void UpdateContactsMainThread()
        {
            // Clear previous contacts
            activeContacts.Clear();
            
            // Check contacts with other holograms
            foreach (var otherHologram in allHolograms)
            {
                if (otherHologram == this || !otherHologram.gameObject.activeInHierarchy)
                    continue;
                    
                CheckContactsWithHologram(otherHologram);
            }
            
            // Check contacts with environment if not avatar-only mode
            if (!enableAvatarToAvatarOnly)
            {
                CheckEnvironmentContacts();
            }
        }
        
        private void UpdateContactsWithJobs()
        {
            // Complete previous job
            if (!contactJobHandle.IsCompleted)
                contactJobHandle.Complete();
                
            // Setup job data
            SetupContactJobData();
            
            // Schedule contact detection job
            var contactJob = new ContactDetectionJob
            {
                contactCheckData = contactCheckData,
                contactResults = contactResults,
                contactRadius = contactRadius
            };
            
            contactJobHandle = contactJob.Schedule(contactCheckData.Length, 32);
            
            // Complete job and process results
            contactJobHandle.Complete();
            ProcessJobResults();
        }
        
        private void CheckContactsWithHologram(HologramContactGlow other)
        {
            for (int i = 0; i < bodyJoints.Length; i++)
            {
                for (int j = 0; j < other.bodyJoints.Length; j++)
                {
                    float distance = Vector3.Distance(bodyJoints[i].position, other.bodyJoints[j].position);
                    
                    if (distance <= contactRadius)
                    {
                        // Determine contact type
                        string contactType = DetermineContactType(i, j);
                        ContactTypeSettings settings = GetContactTypeSettings(contactType);
                        
                        // Create contact
                        var contact = new ActiveContact
                        {
                            worldPosition = bodyJoints[i].position,
                            vertexIndex = FindNearestVertexIndex(bodyJoints[i].position),
                            intensity = settings.intensity * glowIntensity,
                            startTime = Time.time,
                            contactType = contactType,
                            otherAvatar = other
                        };
                        
                        activeContacts.Add(contact);
                        
                        if (logContactEvents)
                            Debug.Log($"Contact: {contactType} between {gameObject.name} and {other.gameObject.name}");
                    }
                }
            }
        }
        
        private void CheckEnvironmentContacts()
        {
            foreach (Transform joint in bodyJoints)
            {
                Collider[] nearbyColliders = Physics.OverlapSphere(joint.position, contactRadius, contactLayers);
                
                foreach (var collider in nearbyColliders)
                {
                    if (collider.transform.IsChildOf(transform))
                        continue; // Skip own colliders
                        
                    var contact = new ActiveContact
                    {
                        worldPosition = joint.position,
                        vertexIndex = FindNearestVertexIndex(joint.position),
                        intensity = glowIntensity * 0.5f, // Reduced intensity for environment
                        startTime = Time.time,
                        contactType = "Environment",
                        otherAvatar = null
                    };
                    
                    activeContacts.Add(contact);
                }
            }
        }
        
        private string DetermineContactType(int jointIndexA, int jointIndexB)
        {
            // Simple contact type determination based on joint indices
            // This could be expanded with more sophisticated logic
            
            string jointA = GetJointName(jointIndexA);
            string jointB = GetJointName(jointIndexB);
            
            if ((jointA.Contains("hand") && jointB.Contains("hand")))
                return "HandToHand";
            else if ((jointA.Contains("hand") && jointB.Contains("head")) || 
                     (jointA.Contains("head") && jointB.Contains("hand")))
                return "HandToFace";
            else if (jointA.Contains("head") && jointB.Contains("head"))
                return "FaceToFace";
            else
                return "BodyToBody";
        }
        
        private string GetJointName(int index)
        {
            foreach (var kvp in jointNameToIndex)
            {
                if (kvp.Value == index)
                    return kvp.Key;
            }
            return "unknown";
        }
        
        private ContactTypeSettings GetContactTypeSettings(string contactType)
        {
            foreach (var settings in contactTypes)
            {
                if (settings.name == contactType)
                    return settings;
            }
            
            // Return default settings
            return new ContactTypeSettings { name = contactType, intensity = 1.0f, radius = contactRadius };
        }
        
        #endregion
        
        #region Vertex Color Management
        
        private int FindNearestVertexIndex(Vector3 worldPosition)
        {
            Vector3 localPosition = transform.InverseTransformPoint(worldPosition);
            float minDistance = float.MaxValue;
            int nearestIndex = 0;
            
            for (int i = 0; i < vertices.Length; i++)
            {
                float distance = Vector3.Distance(vertices[i], localPosition);
                if (distance < minDistance)
                {
                    minDistance = distance;
                    nearestIndex = i;
                }
            }
            
            return nearestIndex;
        }
        
        private void ApplyContactsToVertexColors()
        {
            // Reset vertex colors to base
            Color baseColor = new Color(0f, 0.1f, 0.2f, 1f);
            for (int i = 0; i < vertexColors.Length; i++)
            {
                vertexColors[i] = baseColor;
            }
            
            // Apply contact glows
            foreach (var contact in activeContacts)
            {
                ApplyContactGlow(contact);
            }
            
            meshDataDirty = true;
        }
        
        private void ApplyContactGlow(ActiveContact contact)
        {
            ContactTypeSettings settings = GetContactTypeSettings(contact.contactType);
            Color glowColor = settings.glowColor;
            float radius = settings.radius;
            
            Vector3 contactLocalPos = transform.InverseTransformPoint(contact.worldPosition);
            
            // Apply glow to nearby vertices
            for (int i = 0; i < vertices.Length; i++)
            {
                float distance = Vector3.Distance(vertices[i], contactLocalPos);
                
                if (distance <= radius)
                {
                    float falloff = 1f - (distance / radius);
                    falloff = Mathf.Pow(falloff, 2); // Squared falloff for smoother transition
                    
                    Color currentColor = vertexColors[i];
                    Color targetColor = Color.Lerp(currentColor, glowColor, falloff * contact.intensity);
                    
                    // Use additive blending for overlapping contacts
                    vertexColors[i] = Color.Lerp(currentColor, targetColor, 0.8f);
                    
                    // Ensure alpha channel is used for glow intensity
                    vertexColors[i].r = Mathf.Max(vertexColors[i].r, falloff * contact.intensity);
                }
            }
        }
        
        private void ApplyVertexColors()
        {
            workingMesh.colors = vertexColors;
        }
        
        private void FadeContacts()
        {
            for (int i = activeContacts.Count - 1; i >= 0; i--)
            {
                var contact = activeContacts[i];
                float age = Time.time - contact.startTime;
                
                // Fade contact over time
                if (age > 1f / glowFadeSpeed)
                {
                    activeContacts.RemoveAt(i);
                }
            }
            
            // Update vertex colors with current contacts
            ApplyContactsToVertexColors();
        }
        
        #endregion
        
        #region Job System Implementation
        
        [Unity.Collections.LowLevel.Unsafe.BurstCompile]
        private struct ContactDetectionJob : IJobParallelFor
        {
            [ReadOnly] public NativeArray<ContactCheckData> contactCheckData;
            public NativeArray<ContactResult> contactResults;
            [ReadOnly] public float contactRadius;
            
            public void Execute(int index)
            {
                var checkData = contactCheckData[index];
                var result = new ContactResult { hasContact = false };
                
                // Simplified contact detection for job system
                // In a full implementation, this would check against other avatar positions
                
                contactResults[index] = result;
            }
        }
        
        private void SetupContactJobData()
        {
            if (contactCheckData.IsCreated)
                contactCheckData.Dispose();
            if (contactResults.IsCreated)
                contactResults.Dispose();
                
            contactCheckData = new NativeArray<ContactCheckData>(bodyJoints.Length, Allocator.TempJob);
            contactResults = new NativeArray<ContactResult>(bodyJoints.Length, Allocator.TempJob);
            
            for (int i = 0; i < bodyJoints.Length; i++)
            {
                contactCheckData[i] = new ContactCheckData
                {
                    position = bodyJoints[i].position,
                    radius = contactRadius,
                    jointIndex = i
                };
            }
        }
        
        private void ProcessJobResults()
        {
            activeContacts.Clear();
            
            for (int i = 0; i < contactResults.Length; i++)
            {
                var result = contactResults[i];
                
                if (result.hasContact)
                {
                    var contact = new ActiveContact
                    {
                        worldPosition = result.contactPoint,
                        vertexIndex = FindNearestVertexIndex(result.contactPoint),
                        intensity = glowIntensity,
                        startTime = Time.time,
                        contactType = "Generic",
                        otherAvatar = null
                    };
                    
                    activeContacts.Add(contact);
                }
            }
        }
        
        #endregion
        
        #region Public API
        
        /// <summary>
        /// Manually trigger a contact at a specific world position
        /// </summary>
        public void TriggerContact(Vector3 worldPosition, float intensity = 1.0f, string contactType = "Manual")
        {
            var contact = new ActiveContact
            {
                worldPosition = worldPosition,
                vertexIndex = FindNearestVertexIndex(worldPosition),
                intensity = intensity * glowIntensity,
                startTime = Time.time,
                contactType = contactType,
                otherAvatar = null
            };
            
            activeContacts.Add(contact);
        }
        
        /// <summary>
        /// Enable or disable contact glow system
        /// </summary>
        public void SetContactGlowEnabled(bool enabled)
        {
            this.enabled = enabled;
            
            if (!enabled)
            {
                // Reset to base colors
                InitializeVertexColors();
                ApplyVertexColors();
            }
        }
        
        /// <summary>
        /// Get current number of active contacts
        /// </summary>
        public int GetActiveContactCount()
        {
            return activeContacts.Count;
        }
        
        #endregion
        
        #region Debug Visualization
        
        void OnDrawGizmos()
        {
            if (!showContactGizmos || bodyJoints == null)
                return;
                
            // Draw joint positions
            Gizmos.color = Color.blue;
            foreach (Transform joint in bodyJoints)
            {
                if (joint != null)
                {
                    Gizmos.DrawWireSphere(joint.position, contactRadius * 0.5f);
                }
            }
            
            // Draw active contacts
            Gizmos.color = Color.cyan;
            foreach (var contact in activeContacts)
            {
                Gizmos.DrawSphere(contact.worldPosition, 0.02f);
                
                // Draw glow radius
                Gizmos.color = new Color(0, 1, 1, 0.3f);
                Gizmos.DrawSphere(contact.worldPosition, GetContactTypeSettings(contact.contactType).radius);
                Gizmos.color = Color.cyan;
            }
        }
        
        #endregion
    }
}
