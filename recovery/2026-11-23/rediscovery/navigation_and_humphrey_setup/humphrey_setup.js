/**
 * Baby Detective Humphrey Navigation Setup
 * Complete integration for your adorable tiny detective avatar
 */

// Initialize PubCast Navigation with Humphrey
function initializeHumphreyNavigation(container) {
    
    // Create the base navigation system
    const navigation = new PubCastNavigation({
        container: container,
        walkSpeed: 0.7,        // Baby legs are shorter!
        turnSensitivity: 1.2,  // But babies are wiggly
        websocket: null        // Connect your WebSocket here
    });
    
    // Add Humphrey's detective extensions
    const humphreyExtensions = new HumphreyDetectiveExtensions(navigation);
    
    // Customize rooms for the Wilson investigation
    setupDetectiveStory(navigation);
    
    // Add Humphrey-specific UI elements
    createHumphreyUI(navigation, humphreyExtensions);
    
    // Start the investigation!
    startWilsonMystery(humphreyExtensions);
    
    return { navigation, humphreyExtensions };
}

function setupDetectiveStory(navigation) {
    // Update room descriptions for the detective story
    navigation.rooms.dressing_room.name = "Detective Headquarters";
    navigation.rooms.dressing_room.description = "Humphrey's base of operations. Wilson was last seen here...";
    
    navigation.rooms.green_room.name = "The Lounge";
    navigation.rooms.green_room.description = "Wilson's favorite hangout spot. Check for clues!";
    
    navigation.rooms.studio.name = "The Crime Scene";
    navigation.rooms.studio.description = "Where Wilson disappeared. Evidence might be here...";
    
    navigation.rooms.control_room.name = "Security Office";
    navigation.rooms.control_room.description = "Check the cameras! Maybe they caught the culprit!";
    
    navigation.rooms.pub.name = "The Hideout";
    navigation.rooms.pub.description = "Could Wilson be hiding here? Check every corner!";
}

function createHumphreyUI(navigation, humphrey) {
    // Create detective case panel
    const casePanel = document.createElement('div');
    casePanel.className = 'humphrey-case-panel';
    casePanel.innerHTML = `
        <div class="case-header">
            <h3>🕵️‍♂️ Detective Humphrey's Case File</h3>
        </div>
        <div class="case-content">
            <div class="wilson-status">
                <div class="status-item">
                    <span class="label">Case:</span>
                    <span class="value">Missing Teddy Bear Wilson</span>
                </div>
                <div class="status-item">
                    <span class="label">Clues Found:</span>
                    <span class="value" id="clue-count">0/5</span>
                </div>
                <div class="status-item">
                    <span class="label">Detective Mood:</span>
                    <span class="value" id="humphrey-mood">Determined</span>
                </div>
            </div>
            <div class="case-notes">
                <h4>📝 Case Notes</h4>
                <div id="notes-list" class="notes-container">
                    <em>No notes yet. Start investigating!</em>
                </div>
            </div>
        </div>
    `;
    
    navigation.container.appendChild(casePanel);
    
    // Update UI when Humphrey finds things
    document.addEventListener('humphrey-action', (event) => {
        updateCaseUI(humphrey);
    });
    
    // Periodic UI updates
    setInterval(() => updateCaseUI(humphrey), 1000);
}

function updateCaseUI(humphrey) {
    const clueCount = document.getElementById('clue-count');
    const mood = document.getElementById('humphrey-mood');
    const notesList = document.getElementById('notes-list');
    
    if (clueCount) {
        clueCount.textContent = `${humphrey.getWilsonClueCount()}/5`;
    }
    
    if (mood) {
        const status = humphrey.humphreyStatus();
        mood.textContent = humphrey.isWilsonFound() ? 'Joyful! 🎉' : 
                          status.detectiveMode ? 'Investigating 🔍' : 'Determined';
    }
    
    if (notesList) {
        const notes = humphrey.getCaseNotes();
        if (notes.length > 0) {
            notesList.innerHTML = notes.map(note => `
                <div class="case-note">
                    <div class="note-location">${note.location}</div>
                    <div class="note-text">${note.humphreyNote}</div>
                    <div class="note-time">${note.time}</div>
                </div>
            `).reverse().slice(0, 5).join(''); // Last 5 notes
        }
    }
}

function startWilsonMystery(humphrey) {
    // Opening scene
    setTimeout(() => {
        showDetectiveDialogue([
            "🕵️‍♂️ *Humphrey adjusts his tiny detective hat*",
            "👶 Wilson is missing! My bestest teddy bear friend!",
            "🔍 I need to search every room for clues!",
            "💪 A real detective never gives up! Let's go!"
        ]);
    }, 2000);
}

function showDetectiveDialogue(lines) {
    let index = 0;
    
    function showNextLine() {
        if (index < lines.length) {
            // Create dialogue bubble
            const bubble = document.createElement('div');
            bubble.className = 'detective-dialogue fade-in';
            bubble.textContent = lines[index];
            document.body.appendChild(bubble);
            
            // Position bubble
            bubble.style.position = 'fixed';
            bubble.style.top = '50%';
            bubble.style.left = '50%';
            bubble.style.transform = 'translate(-50%, -50%)';
            bubble.style.zIndex = '9999';
            
            // Remove after 3 seconds
            setTimeout(() => {
                bubble.style.opacity = '0';
                setTimeout(() => {
                    if (bubble.parentNode) {
                        bubble.parentNode.removeChild(bubble);
                    }
                }, 300);
            }, 2500);
            
            index++;
            setTimeout(showNextLine, 3000);
        }
    }
    
    showNextLine();
}

// CSS for Humphrey's UI
const humphreyCSSStyle = `
    .humphrey-case-panel {
        position: absolute;
        top: 20px;
        left: 20px;
        background: linear-gradient(135deg, 
            rgba(139, 69, 19, 0.95) 0%, 
            rgba(160, 82, 45, 0.95) 100%);
        border: 2px solid rgba(255, 215, 0, 0.5);
        border-radius: 8px;
        padding: 15px;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        box-shadow: 
            0 4px 12px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        min-width: 250px;
        max-width: 300px;
        z-index: 1000;
        font-family: 'Comic Sans MS', cursive;
    }
    
    .case-header {
        text-align: center;
        margin-bottom: 10px;
    }
    
    .case-header h3 {
        color: #FFD700;
        margin: 0;
        font-size: 14px;
        text-shadow: 0 0 8px rgba(255, 215, 0, 0.3);
    }
    
    .wilson-status {
        background: rgba(0, 0, 0, 0.3);
        border-radius: 4px;
        padding: 8px;
        margin-bottom: 10px;
    }
    
    .status-item {
        display: flex;
        justify-content: space-between;
        color: #FFF;
        font-size: 11px;
        margin-bottom: 4px;
    }
    
    .status-item .label {
        font-weight: bold;
        color: #FFD700;
    }
    
    .case-notes h4 {
        color: #FFD700;
        margin: 8px 0 5px 0;
        font-size: 12px;
    }
    
    .notes-container {
        max-height: 120px;
        overflow-y: auto;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 3px;
        padding: 5px;
    }
    
    .case-note {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        padding: 4px 6px;
        margin-bottom: 4px;
        font-size: 10px;
    }
    
    .note-location {
        color: #FFD700;
        font-weight: bold;
        font-size: 9px;
    }
    
    .note-text {
        color: #FFF;
        font-style: italic;
        margin: 2px 0;
    }
    
    .note-time {
        color: #CCC;
        font-size: 8px;
        text-align: right;
    }
    
    .detective-dialogue {
        background: linear-gradient(135deg, 
            rgba(139, 69, 19, 0.95) 0%, 
            rgba(160, 82, 45, 0.95) 100%);
        border: 2px solid rgba(255, 215, 0, 0.7);
        border-radius: 12px;
        padding: 15px 20px;
        color: #FFF;
        font-family: 'Comic Sans MS', cursive;
        font-size: 14px;
        text-align: center;
        box-shadow: 
            0 4px 12px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        max-width: 400px;
        transition: opacity 0.3s ease;
    }
    
    @media (max-width: 768px) {
        .humphrey-case-panel {
            top: 10px;
            left: 10px;
            right: 10px;
            max-width: none;
        }
        
        .detective-dialogue {
            margin: 0 20px;
        }
    }
`;

// Add Humphrey CSS to document
function addHumphreyStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = humphreyCSSStyle;
    document.head.appendChild(styleElement);
}

// Complete initialization function
function setupHumphreyStudio(containerId = 'navigation-container') {
    // Add styles
    addHumphreyStyles();
    
    // Get container
    const container = document.getElementById(containerId) || document.body;
    
    // Initialize Humphrey navigation
    const humphreySystem = initializeHumphreyNavigation(container);
    
    console.log("🕵️‍♂️ Baby Detective Humphrey is ready to find Wilson!");
    
    return humphreySystem;
}

// Usage example:
// const humphrey = setupHumphreyStudio('my-container');

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeHumphreyNavigation,
        setupHumphreyStudio,
        HumphreyDetectiveExtensions
    };
} else if (typeof window !== 'undefined') {
    window.setupHumphreyStudio = setupHumphreyStudio;
    window.initializeHumphreyNavigation = initializeHumphreyNavigation;
}
