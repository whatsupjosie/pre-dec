/**
 * HUMPHREY AVATAR MAKER - PUBCAST MASCOT SYSTEM
 * Baby Detective Humphrey 3D Character Customization
 * Based on Curtsy's "Too Much to Bear" character designs
 */

class HumphreyAvatarMaker {
    constructor(containerElement) {
        this.container = containerElement;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.humphrey = null;
        this.props = {
            magnifyingGlass: null,
            detectiveCoat: null,
            notebook: null
        };
        
        // Character customization options
        this.customization = {
            coatColor: '#8B4513', // Detective brown
            hatStyle: 'classic', // classic, fedora, none
            expression: 'curious', // curious, sad, determined, investigating
            pose: 'standing', // standing, investigating, thinking
            props: ['magnifyingGlass'] // available props
        };
        
        this.init();
    }
    
    async init() {
        // Check if Three.js is available
        if (typeof THREE === 'undefined') {
            console.error('🚨 Three.js not loaded! Cannot initialize Humphrey Avatar Maker.');
            this.showError('Three.js library failed to load. Please refresh the page.');
            return;
        }
        
        try {
            await this.setupThreeJS();
            await this.loadHumphreyModel();
            await this.setupControls();
            await this.setupCustomizationUI();
            this.animate();
            console.log('✅ Detective Humphrey Avatar Maker initialized successfully!');
        } catch (error) {
            console.error('🚨 Error initializing Humphrey Avatar Maker:', error);
            this.showError(`Failed to initialize avatar maker: ${error.message}`);
        }
    }
    
    showError(message) {
        if (this.container) {
            this.container.innerHTML = `
                <div class="humphrey-error">
                    <div class="error-icon">🔍💔</div>
                    <h3>Detective Humphrey Investigation Failed</h3>
                    <p>${message}</p>
                    <button onclick="location.reload()" class="retry-btn">Try Again</button>
                </div>
            `;
        }
    }
    
    async setupThreeJS() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x2a1810); // Noir brown
        
        // Camera setup - positioned to show baby detective
        this.camera = new THREE.PerspectiveCamera(
            75, 
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 1, 3); // Eye level with baby Humphrey
        
        // Renderer setup
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.container.appendChild(this.renderer.domElement);
        
        // Lighting - Noir style dramatic lighting
        this.setupNoirLighting();
    }
    
    setupNoirLighting() {
        // Key light - harsh side lighting for noir shadows
        const keyLight = new THREE.DirectionalLight(0xffeecc, 1.2);
        keyLight.position.set(5, 10, 5);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 2048;
        keyLight.shadow.mapSize.height = 2048;
        this.scene.add(keyLight);
        
        // Fill light - soft ambient for baby-friendly lighting
        const fillLight = new THREE.AmbientLight(0x404040, 0.4);
        this.scene.add(fillLight);
        
        // Rim light - dramatic edge lighting
        const rimLight = new THREE.DirectionalLight(0x8888ff, 0.8);
        rimLight.position.set(-5, 2, -5);
        this.scene.add(rimLight);
    }
    
    async loadHumphreyModel() {
        // Note: This would load the actual 3D model created from Curtsy's art
        // For now, creating a placeholder that matches the character design
        
        await this.createHumphreyPlaceholder();
        await this.createDetectiveProps();
    }
    
    async createHumphreyPlaceholder() {
        // Create baby proportions based on the artwork
        const group = new THREE.Group();
        
        // Head - larger proportion for baby
        const headGeometry = new THREE.SphereGeometry(0.4, 32, 16);
        const headMaterial = new THREE.MeshPhongMaterial({ 
            color: 0xfdbcb4, // Baby skin tone
            shininess: 10
        });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        head.position.y = 1.2;
        head.castShadow = true;
        group.add(head);
        
        // Body - baby proportions
        const bodyGeometry = new THREE.CylinderGeometry(0.25, 0.35, 0.8, 8);
        const bodyMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x8B4513 // Detective coat brown
        });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        body.position.y = 0.6;
        body.castShadow = true;
        group.add(body);
        
        // Arms - short baby arms
        for (let side of [-1, 1]) {
            const armGeometry = new THREE.CylinderGeometry(0.1, 0.12, 0.5, 8);
            const arm = new THREE.Mesh(armGeometry, bodyMaterial);
            arm.position.set(side * 0.4, 0.8, 0);
            arm.rotation.z = side * 0.2;
            arm.castShadow = true;
            group.add(arm);
        }
        
        // Legs - stubby baby legs
        for (let side of [-1, 1]) {
            const legGeometry = new THREE.CylinderGeometry(0.12, 0.15, 0.4, 8);
            const legMaterial = new THREE.MeshPhongMaterial({ color: 0x333333 });
            const leg = new THREE.Mesh(legGeometry, legMaterial);
            leg.position.set(side * 0.15, 0.2, 0);
            leg.castShadow = true;
            group.add(leg);
        }
        
        // Detective hat
        const hatGeometry = new THREE.CylinderGeometry(0.35, 0.35, 0.1, 16);
        const hatMaterial = new THREE.MeshPhongMaterial({ color: 0x2F1B14 });
        const hat = new THREE.Mesh(hatGeometry, hatMaterial);
        hat.position.y = 1.5;
        hat.castShadow = true;
        group.add(hat);
        
        this.humphrey = group;
        this.scene.add(group);
    }
    
    async createDetectiveProps() {
        // Magnifying glass - Humphrey's signature prop
        const handle = new THREE.CylinderGeometry(0.02, 0.02, 0.3, 8);
        const handleMaterial = new THREE.MeshPhongMaterial({ color: 0x8B4513 });
        const magnifyingHandle = new THREE.Mesh(handle, handleMaterial);
        
        const lensGeometry = new THREE.RingGeometry(0.12, 0.15, 16);
        const lensMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x87CEEB, 
            transparent: true, 
            opacity: 0.3 
        });
        const lens = new THREE.Mesh(lensGeometry, lensMaterial);
        lens.position.y = 0.2;
        
        const glassGroup = new THREE.Group();
        glassGroup.add(magnifyingHandle);
        glassGroup.add(lens);
        glassGroup.position.set(0.5, 0.8, 0.2);
        glassGroup.rotation.z = -0.3;
        
        this.props.magnifyingGlass = glassGroup;
        this.humphrey.add(glassGroup);
    }
    
    setupControls() {
        // Orbit controls for 3D view - with fallback
        try {
            if (typeof THREE.OrbitControls !== 'undefined') {
                this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
                this.controls.enableDamping = true;
                this.controls.dampingFactor = 0.25;
                this.controls.minDistance = 2;
                this.controls.maxDistance = 6;
            } else if (window.OrbitControls) {
                // Fallback for different loading methods
                this.controls = new OrbitControls(this.camera, this.renderer.domElement);
                this.controls.enableDamping = true;
                this.controls.dampingFactor = 0.25;
                this.controls.minDistance = 2;
                this.controls.maxDistance = 6;
            } else {
                console.warn('⚠️  OrbitControls not available, using basic camera controls');
                this.setupBasicControls();
            }
        } catch (error) {
            console.warn('⚠️  Error setting up OrbitControls:', error);
            this.setupBasicControls();
        }
    }
    
    setupBasicControls() {
        // Basic mouse/touch controls as fallback
        let isDragging = false;
        let previousMousePosition = { x: 0, y: 0 };
        
        this.renderer.domElement.addEventListener('mousedown', (e) => {
            isDragging = true;
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });
        
        this.renderer.domElement.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const deltaMove = {
                x: e.clientX - previousMousePosition.x,
                y: e.clientY - previousMousePosition.y
            };
            
            // Rotate camera around the character
            const rotationSpeed = 0.005;
            this.camera.position.x = this.camera.position.x * Math.cos(deltaMove.x * rotationSpeed) - this.camera.position.z * Math.sin(deltaMove.x * rotationSpeed);
            this.camera.position.z = this.camera.position.x * Math.sin(deltaMove.x * rotationSpeed) + this.camera.position.z * Math.cos(deltaMove.x * rotationSpeed);
            this.camera.lookAt(0, 1, 0); // Look at Humphrey's center
            
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });
        
        this.renderer.domElement.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }
    
    setupCustomizationUI() {
        // Create customization panel
        const panel = document.createElement('div');
        panel.className = 'humphrey-customization-panel';
        panel.innerHTML = `
            <div class="customization-header">
                <h3>🕵️‍♂️ Detective Humphrey</h3>
                <p class="subtitle">Rear View Foresight Mascot</p>
            </div>
            
            <div class="customization-group">
                <label>Expression:</label>
                <select id="humphrey-expression">
                    <option value="curious">Curious</option>
                    <option value="determined">Determined</option>
                    <option value="investigating">Investigating</option>
                    <option value="sad">Missing Wilson</option>
                </select>
            </div>
            
            <div class="customization-group">
                <label>Pose:</label>
                <select id="humphrey-pose">
                    <option value="standing">Standing</option>
                    <option value="investigating">Investigating</option>
                    <option value="thinking">Thinking</option>
                    <option value="walking">Walking</option>
                </select>
            </div>
            
            <div class="customization-group">
                <label>Detective Props:</label>
                <div class="props-checkboxes">
                    <label><input type="checkbox" id="prop-magnifying" checked> Magnifying Glass</label>
                    <label><input type="checkbox" id="prop-notebook"> Notebook</label>
                    <label><input type="checkbox" id="prop-wilson"> Wilson (Teddy Bear)</label>
                </div>
            </div>
            
            <div class="customization-group">
                <label>Coat Color:</label>
                <input type="color" id="humphrey-coat-color" value="#8B4513">
            </div>
            
            <div class="action-buttons">
                <button id="save-humphrey">Save Detective</button>
                <button id="use-in-rooms">Use in Rooms</button>
            </div>
        `;
        
        this.container.appendChild(panel);
        this.bindCustomizationEvents();
    }
    
    bindCustomizationEvents() {
        // Expression changes
        document.getElementById('humphrey-expression').addEventListener('change', (e) => {
            this.updateExpression(e.target.value);
        });
        
        // Pose changes
        document.getElementById('humphrey-pose').addEventListener('change', (e) => {
            this.updatePose(e.target.value);
        });
        
        // Prop toggles
        document.getElementById('prop-magnifying').addEventListener('change', (e) => {
            this.toggleProp('magnifyingGlass', e.target.checked);
        });
        
        // Coat color
        document.getElementById('humphrey-coat-color').addEventListener('change', (e) => {
            this.updateCoatColor(e.target.value);
        });
        
        // Save configuration
        document.getElementById('save-humphrey').addEventListener('click', () => {
            this.saveConfiguration();
        });
        
        // Use in rooms
        document.getElementById('use-in-rooms').addEventListener('click', () => {
            this.deployToRooms();
        });
    }
    
    updateExpression(expression) {
        // Update facial features based on expression
        // This would modify the head mesh/texture
        console.log(`Updating Humphrey's expression to: ${expression}`);
        this.customization.expression = expression;
    }
    
    updatePose(pose) {
        // Update character pose
        if (!this.humphrey) return;
        
        switch(pose) {
            case 'investigating':
                this.humphrey.rotation.y = 0.3;
                if (this.props.magnifyingGlass) {
                    this.props.magnifyingGlass.position.set(0.3, 1.0, 0.5);
                }
                break;
            case 'thinking':
                this.humphrey.rotation.y = -0.2;
                break;
            case 'walking':
                // Add subtle animation here
                break;
            default:
                this.humphrey.rotation.y = 0;
        }
        this.customization.pose = pose;
    }
    
    toggleProp(propName, enabled) {
        if (this.props[propName]) {
            this.props[propName].visible = enabled;
        }
    }
    
    updateCoatColor(color) {
        // Update coat material color
        if (this.humphrey) {
            this.humphrey.children.forEach(child => {
                if (child.material && child.material.color) {
                    if (child === this.humphrey.children[1]) { // Body
                        child.material.color.setHex(color.replace('#', '0x'));
                    }
                }
            });
        }
        this.customization.coatColor = color;
    }
    
    saveConfiguration() {
        // Save to localStorage and backend
        const config = {
            ...this.customization,
            timestamp: new Date().toISOString()
        };
        
        localStorage.setItem('humphrey_avatar_config', JSON.stringify(config));
        
        // Also save to backend
        fetch('/api/avatar/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        console.log('Humphrey configuration saved!', config);
    }
    
    deployToRooms() {
        // Deploy this Humphrey configuration to room navigation
        this.saveConfiguration();
        
        // Update green room avatar
        window.postMessage({
            type: 'UPDATE_ROOM_AVATAR',
            avatar: 'humphrey',
            config: this.customization
        }, '*');
        
        alert('Detective Humphrey is now your avatar in all rooms! 🕵️‍♂️');
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        if (this.controls) {
            this.controls.update();
        }
        
        // Add subtle breathing animation
        if (this.humphrey) {
            const time = Date.now() * 0.001;
            this.humphrey.children[1].scale.y = 1 + Math.sin(time * 2) * 0.02; // Body breathing
        }
        
        this.renderer.render(this.scene, this.camera);
    }
    
    resize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}

// Export for use in dressing room
window.HumphreyAvatarMaker = HumphreyAvatarMaker;
