// ========================================
// GREEN ROOM - HALLWAY CONNECTOR
// Simple side-scrolling navigation
// ========================================

class GreenRoom {
    constructor() {
        // Player elements
        this.player = document.getElementById('player');
        this.doorPrompt = document.getElementById('door-prompt');
        this.instructions = document.getElementById('instructions');
        
        // Doors
        this.dressingDoor = document.getElementById('dressing-door');
        this.controlDoor = document.getElementById('control-door');
        
        // Player state
        this.playerX = 50; // Percentage from left (50% = center)
        this.moveSpeed = 0.5; // Percentage per frame
        this.facingRight = true;
        
        // Input state
        this.keys = {};
        
        // Door proximity
        this.nearDoor = null;
        this.doorThreshold = 200; // pixels
        
        // Animation frame
        this.animationFrame = null;
        
        this.init();
    }
    
    init() {
        this.setupControls();
        this.startGameLoop();
        this.showInstructions();
    }
    
    // ========================================
    // CONTROLS
    // ========================================
    
    setupControls() {
        // Keyboard input
        window.addEventListener('keydown', (e) => {
            this.keys[e.code] = true;
            
            // Enter door
            if ((e.code === 'Space' || e.code === 'Enter') && this.nearDoor) {
                e.preventDefault();
                this.enterDoor(this.nearDoor);
            }
        });
        
        window.addEventListener('keyup', (e) => {
            this.keys[e.code] = false;
        });
        
        // Close instructions
        document.getElementById('close-instructions').addEventListener('click', () => {
            this.hideInstructions();
        });
        
        // Click doors directly
        this.dressingDoor.addEventListener('click', () => {
            this.goToDressingRoom();
        });
        
        this.controlDoor.addEventListener('click', () => {
            this.goToControlRoom();
        });
    }
    
    // ========================================
    // GAME LOOP
    // ========================================
    
    startGameLoop() {
        const loop = () => {
            this.update();
            this.animationFrame = requestAnimationFrame(loop);
        };
        loop();
    }
    
    update() {
        this.handleMovement();
        this.updatePlayerPosition();
        this.checkDoorProximity();
    }
    
    handleMovement() {
        let moving = false;
        
        // Left movement (A or ArrowLeft)
        if (this.keys['KeyA'] || this.keys['ArrowLeft']) {
            this.playerX = Math.max(5, this.playerX - this.moveSpeed);
            this.facingRight = false;
            moving = true;
        }
        
        // Right movement (D or ArrowRight)
        if (this.keys['KeyD'] || this.keys['ArrowRight']) {
            this.playerX = Math.min(95, this.playerX + this.moveSpeed);
            this.facingRight = true;
            moving = true;
        }
        
        // Update player class for animation
        if (moving) {
            this.player.classList.add('walking');
        } else {
            this.player.classList.remove('walking');
        }
        
        // Update facing direction
        if (this.facingRight) {
            this.player.classList.remove('facing-left');
            this.player.classList.add('facing-right');
        } else {
            this.player.classList.add('facing-left');
            this.player.classList.remove('facing-right');
        }
    }
    
    updatePlayerPosition() {
        this.player.style.left = this.playerX + '%';
    }
    
    // ========================================
    // DOOR PROXIMITY & INTERACTION
    // ========================================
    
    checkDoorProximity() {
        const playerRect = this.player.getBoundingClientRect();
        const playerCenterX = playerRect.left + playerRect.width / 2;
        
        const dressingRect = this.dressingDoor.getBoundingClientRect();
        const dressingCenterX = dressingRect.left + dressingRect.width / 2;
        const dressingDistance = Math.abs(playerCenterX - dressingCenterX);
        
        const controlRect = this.controlDoor.getBoundingClientRect();
        const controlCenterX = controlRect.left + controlRect.width / 2;
        const controlDistance = Math.abs(playerCenterX - controlCenterX);
        
        // Check which door is closest
        if (dressingDistance < this.doorThreshold && dressingDistance < controlDistance) {
            this.nearDoor = 'dressing';
            this.showDoorPrompt();
        } else if (controlDistance < this.doorThreshold && controlDistance < dressingDistance) {
            this.nearDoor = 'control';
            this.showDoorPrompt();
        } else {
            this.nearDoor = null;
            this.hideDoorPrompt();
        }
    }
    
    showDoorPrompt() {
        this.doorPrompt.classList.add('visible');
    }
    
    hideDoorPrompt() {
        this.doorPrompt.classList.remove('visible');
    }
    
    enterDoor(doorType) {
        if (doorType === 'dressing') {
            this.goToDressingRoom();
        } else if (doorType === 'control') {
            this.goToControlRoom();
        }
    }
    
    // ========================================
    // NAVIGATION
    // ========================================
    
    goToDressingRoom() {
        // Fade out
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '0';
        
        setTimeout(() => {
            window.location.href = '/dressing';
        }, 500);
    }
    
    goToControlRoom() {
        // Fade out
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '0';
        
        setTimeout(() => {
            window.location.href = '/control-room';
        }, 500);
    }
    
    // ========================================
    // INSTRUCTIONS
    // ========================================
    
    showInstructions() {
        // Check if user has seen instructions before
        const hasSeenInstructions = localStorage.getItem('greenroom_instructions_seen');
        
        if (hasSeenInstructions) {
            this.hideInstructions();
        } else {
            this.instructions.classList.remove('hidden');
        }
    }
    
    hideInstructions() {
        this.instructions.classList.add('hidden');
        localStorage.setItem('greenroom_instructions_seen', 'true');
    }
}

// ========================================
// INITIALIZE
// ========================================

let greenRoom;

document.addEventListener('DOMContentLoaded', () => {
    greenRoom = new GreenRoom();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (greenRoom && greenRoom.animationFrame) {
        cancelAnimationFrame(greenRoom.animationFrame);
    }
});
