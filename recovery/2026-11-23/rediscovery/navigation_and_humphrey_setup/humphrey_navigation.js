/**
 * Baby Detective Humphrey Navigation Extensions
 * Special movement and interactions for our adorable tiny detective
 */

class HumphreyDetectiveExtensions {
    constructor(navigationSystem) {
        this.nav = navigationSystem;
        this.detectiveMode = false;
        this.magnifyingGlass = false;
        this.caseNotes = [];
        this.wilsonClues = 0;
        this.lastInvestigation = null;
        
        // Humphrey-specific settings
        this.humphreySettings = {
            // Baby detective has shorter stride and waddle
            walkSpeed: 0.7,        // Slower because tiny legs
            runSpeed: 1.2,         // Still pretty slow even when running
            waddleAmount: 0.3,     // Side-to-side baby waddle
            stepHeight: 0.1,       // Little bouncy steps
            detectiveMode: false,
            
            // Detective equipment
            equipment: {
                magnifyingGlass: true,
                notepad: true,
                hat: 'oversized_fedora',
                coat: 'tiny_trench_coat',
                badge: 'baby_detective_badge'
            },
            
            // Emotional states
            mood: 'determined',    // looking for Wilson
            wilsonMissing: true,
            braveryLevel: 'maximum'
        };
        
        this.initHumphrey();
    }
    
    initHumphrey() {
        // Override the default player drawing with Humphrey
        this.nav.drawPlayer = this.drawHumphreyDetective.bind(this);
        
        // Add Humphrey-specific movement
        this.nav.updateMovement = this.updateHumphreyMovement.bind(this);
        
        // Add detective interactions
        this.nav.interact = this.humphreyInvestigate.bind(this);
        
        // Apply Humphrey settings
        this.nav.setWalkSpeed(this.humphreySettings.walkSpeed);
        
        // Add detective zones to rooms
        this.addDetectiveZones();
        
        // Start Humphrey's mission
        this.startWilsonSearch();
    }
    
    addDetectiveZones() {
        // Add Wilson clues to each room
        const clueZones = {
            dressing_room: [
                { type: 'wilson_clue', x: 200, y: 400, width: 60, height: 60, 
                  action: 'investigate_clue', clue: 'teddy_bear_fur' },
                { type: 'suspicious_spot', x: 500, y: 200, width: 80, height: 80,
                  action: 'examine_suspicious', evidence: 'tiny_footprints' }
            ],
            green_room: [
                { type: 'wilson_clue', x: 600, y: 400, width: 60, height: 60,
                  action: 'investigate_clue', clue: 'wilson_favorite_spot' },
                { type: 'witness', x: 300, y: 200, width: 100, height: 100,
                  action: 'interview_witness', witness: 'stuffed_elephant' }
            ],
            studio: [
                { type: 'crime_scene', x: 500, y: 300, width: 200, height: 150,
                  action: 'analyze_crime_scene', evidence: 'last_seen_here' }
            ],
            control_room: [
                { type: 'security_footage', x: 300, y: 200, width: 150, height: 100,
                  action: 'review_footage', evidence: 'security_camera' }
            ],
            pub: [
                { type: 'wilson_hideout', x: 700, y: 300, width: 120, height: 120,
                  action: 'search_hideout', evidence: 'wilson_might_be_here' }
            ]
        };
        
        // Add detective zones to each room
        Object.keys(clueZones).forEach(roomId => {
            if (this.nav.rooms[roomId]) {
                this.nav.rooms[roomId].zones = [
                    ...this.nav.rooms[roomId].zones,
                    ...clueZones[roomId]
                ];
            }
        });
    }
    
    updateHumphreyMovement(deltaTime) {
        if (!this.nav.player.canMove) return;
        
        // Calculate target velocity with baby characteristics
        const baseSpeed = this.humphreySettings.walkSpeed * (this.nav.keys.shift ? 1.8 : 1.0);
        
        // Add detective urgency boost when Wilson clues are near
        const urgencyBoost = this.isNearClue() ? 1.3 : 1.0;
        const speed = baseSpeed * urgencyBoost;
        
        this.nav.movement.targetVelocity.x = 0;
        this.nav.movement.targetVelocity.y = 0;
        
        // Screen-relative movement with baby waddle
        if (this.nav.keys.w) this.nav.movement.targetVelocity.y = -speed;
        if (this.nav.keys.s) this.nav.movement.targetVelocity.y = speed;
        if (this.nav.keys.a) this.nav.movement.targetVelocity.x = -speed;
        if (this.nav.keys.d) this.nav.movement.targetVelocity.x = speed;
        
        // Normalize diagonal movement
        if (this.nav.movement.targetVelocity.x !== 0 && this.nav.movement.targetVelocity.y !== 0) {
            const length = Math.sqrt(this.nav.movement.targetVelocity.x ** 2 + this.nav.movement.targetVelocity.y ** 2);
            this.nav.movement.targetVelocity.x = (this.nav.movement.targetVelocity.x / length) * speed;
            this.nav.movement.targetVelocity.y = (this.nav.movement.targetVelocity.y / length) * speed;
        }
        
        // Baby detective acceleration (a bit bouncy)
        const accel = this.nav.movement.targetVelocity.x !== 0 || this.nav.movement.targetVelocity.y !== 0 
                     ? this.nav.movement.acceleration * 1.2 : this.nav.movement.deceleration;
        
        this.nav.movement.currentVelocity.x = this.nav.lerp(this.nav.movement.currentVelocity.x, this.nav.movement.targetVelocity.x, accel);
        this.nav.movement.currentVelocity.y = this.nav.lerp(this.nav.movement.currentVelocity.y, this.nav.movement.targetVelocity.y, accel);
        
        // Add baby waddle when moving
        let waddleX = 0;
        let waddleY = 0;
        if (this.nav.player.moving) {
            const waddleTime = performance.now() * 0.008; // Waddle frequency
            waddleX = Math.sin(waddleTime) * this.humphreySettings.waddleAmount;
            waddleY = Math.cos(waddleTime * 0.5) * this.humphreySettings.stepHeight;
        }
        
        // Apply movement with waddle
        const newPosition = {
            x: this.nav.player.position.x + (this.nav.movement.currentVelocity.x + waddleX) * deltaTime * 60,
            y: this.nav.player.position.y + (this.nav.movement.currentVelocity.y) * deltaTime * 60,
            z: this.nav.player.position.z + waddleY
        };
        
        // Check bounds and collision
        if (this.nav.isValidPosition(newPosition)) {
            this.nav.setPlayerPosition(newPosition);
            this.nav.player.moving = Math.abs(this.nav.movement.currentVelocity.x) > 0.1 || Math.abs(this.nav.movement.currentVelocity.y) > 0.1;
            
            // Update rotation based on movement direction
            if (this.nav.player.moving) {
                this.nav.player.rotation = Math.atan2(this.nav.movement.currentVelocity.y, this.nav.movement.currentVelocity.x);
            }
        }
        
        // Check for Wilson clues and detective zones
        this.checkDetectiveZones();
        this.updateDetectiveStatus();
    }
    
    drawHumphreyDetective() {
        const ctx = this.nav.ctx;
        const pos = this.nav.player.position;
        
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(this.nav.player.rotation);
        
        // Humphrey's body (chubby toddler)
        const bodyColor = this.nav.player.moving ? '#8B4513' : '#A0522D'; // Brown detective coat
        
        // Main body (bigger for baby proportions)
        ctx.fillStyle = bodyColor;
        ctx.beginPath();
        ctx.ellipse(0, 0, 18, 22, 0, 0, Math.PI * 2);
        ctx.fill();
        
        // Detective coat details
        ctx.strokeStyle = '#654321';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Tiny detective badge
        ctx.fillStyle = '#FFD700';
        ctx.beginPath();
        ctx.arc(-8, -8, 3, 0, Math.PI * 2);
        ctx.fill();
        
        // Oversized detective hat
        ctx.fillStyle = '#2F1B14';
        ctx.beginPath();
        ctx.ellipse(0, -25, 25, 8, 0, 0, Math.PI * 2); // Hat brim
        ctx.fill();
        ctx.fillRect(-15, -35, 30, 15); // Hat crown
        
        // Hat band
        ctx.fillStyle = '#8B4513';
        ctx.fillRect(-15, -28, 30, 3);
        
        // Little face under the hat
        ctx.fillStyle = '#FDBCB4'; // Baby skin tone
        ctx.beginPath();
        ctx.arc(0, -15, 8, 0, Math.PI * 2);
        ctx.fill();
        
        // Determined detective eyes
        ctx.fillStyle = '#000000';
        ctx.beginPath();
        ctx.arc(-3, -17, 2, 0, Math.PI * 2);
        ctx.arc(3, -17, 2, 0, Math.PI * 2);
        ctx.fill();
        
        // Serious detective mouth (looking for Wilson)
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(0, -12, 3, 0, Math.PI);
        ctx.stroke();
        
        // Magnifying glass (if investigating)
        if (this.detectiveMode || this.magnifyingGlass) {
            ctx.save();
            ctx.translate(20, -10);
            
            // Handle
            ctx.strokeStyle = '#8B4513';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(8, 8);
            ctx.lineTo(15, 15);
            ctx.stroke();
            
            // Glass circle
            ctx.strokeStyle = '#4169E1';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(0, 0, 8, 0, Math.PI * 2);
            ctx.stroke();
            
            // Glass shine
            ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.beginPath();
            ctx.arc(-3, -3, 3, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.restore();
        }
        
        // Case notepad (if taking notes)
        if (this.caseNotes.length > 0) {
            ctx.save();
            ctx.translate(-20, 0);
            
            ctx.fillStyle = '#FFFACD';
            ctx.fillRect(0, 0, 12, 16);
            
            ctx.strokeStyle = '#000000';
            ctx.lineWidth = 1;
            ctx.strokeRect(0, 0, 12, 16);
            
            // Tiny writing lines
            ctx.beginPath();
            for (let i = 1; i <= 3; i++) {
                ctx.moveTo(1, i * 4);
                ctx.lineTo(11, i * 4);
            }
            ctx.stroke();
            
            ctx.restore();
        }
        
        // Direction indicator (baby footsteps)
        if (this.nav.player.moving) {
            ctx.strokeStyle = '#8B4513';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(12, 2, 2, 0, Math.PI * 2);
            ctx.arc(15, -2, 2, 0, Math.PI * 2);
            ctx.stroke();
        }
        
        // Wilson search indicator (sad expression when Wilson not found)
        if (this.humphreySettings.wilsonMissing) {
            ctx.save();
            ctx.translate(0, -40);
            ctx.fillStyle = 'rgba(0, 0, 255, 0.7)';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Looking for Wilson...', 0, 0);
            ctx.restore();
        }
        
        ctx.restore();
    }
    
    humphreyInvestigate() {
        const room = this.nav.rooms[this.nav.player.room];
        let foundSomething = false;
        
        for (const zone of room.zones || []) {
            if (this.nav.isInZone(this.nav.player.position, zone)) {
                if (zone.type.includes('wilson') || zone.type.includes('clue') || zone.type.includes('suspicious')) {
                    this.conductDetectiveWork(zone);
                    foundSomething = true;
                } else {
                    // Regular interaction but with Humphrey's baby detective personality
                    this.humphreyRegularInteraction(zone);
                    foundSomething = true;
                }
                break;
            }
        }
        
        if (!foundSomething) {
            // Humphrey examines the general area
            this.generalInvestigation();
        }
    }
    
    conductDetectiveWork(zone) {
        this.detectiveMode = true;
        this.magnifyingGlass = true;
        
        const detectiveLines = [
            "Hmm... interesting... *adjusts tiny hat*",
            "*pulls out magnifying glass* What's this clue?",
            "Wilson was here! I can feel it!",
            "*takes notes in tiny notepad*",
            "The case is getting clearer...",
            "*sniffles a little* Wilson, where are you?",
            "A detective's work is never done!",
            "*waddles closer to examine*"
        ];
        
        const randomLine = detectiveLines[Math.floor(Math.random() * detectiveLines.length)];
        
        // Add to case notes
        this.caseNotes.push({
            location: this.nav.player.room,
            clue: zone.clue || zone.evidence || zone.type,
            time: new Date().toLocaleTimeString(),
            humphreyNote: randomLine
        });
        
        if (zone.type === 'wilson_clue') {
            this.wilsonClues++;
            this.nav.showStatus(`🕵️ Humphrey found a Wilson clue! (${this.wilsonClues}/5)`, 'success');
            
            if (this.wilsonClues >= 5) {
                this.foundWilson();
            }
        } else {
            this.nav.showStatus(`🔍 ${randomLine}`, 'info');
        }
        
        // Turn off detective mode after investigation
        setTimeout(() => {
            this.detectiveMode = false;
            this.magnifyingGlass = false;
        }, 3000);
        
        this.lastInvestigation = performance.now();
    }
    
    humphreyRegularInteraction(zone) {
        const babyDetectiveResponses = {
            wardrobe: "*climbs up to reach clothes* These are too big for me!",
            mirror: "*adjusts detective hat in mirror* Looking professional!",
            desk: "*stands on tippy toes* Important detective business!",
            couch: "*bounces on couch* This is comfy but Wilson's not here...",
            coffee: "*sniffs* This smells like grown-up juice!",
            stage: "*waddles onto stage* Ladies and gentlemen, I'm looking for Wilson!",
            bar: "*orders* One chocolate milk, please! Detective work is thirsty!",
            games: "*examines games* Maybe Wilson is hiding in here?"
        };
        
        const response = babyDetectiveResponses[zone.type] || 
                        "*investigates curiously* Hmm, this might be a clue!";
        
        this.nav.showStatus(`👶🕵️ ${response}`, 'info');
        
        // Trigger action event with Humphrey context
        document.dispatchEvent(new CustomEvent('humphrey-action', {
            detail: { 
                action: zone.action, 
                zone, 
                room: this.nav.player.room, 
                position: this.nav.player.position,
                humphreyNote: response,
                detectiveMode: this.detectiveMode
            }
        }));
    }
    
    generalInvestigation() {
        const generalDetectiveLines = [
            "*looks around with magnifying glass* Hmm...",
            "*sniffs the air* Wilson might have been here...",
            "*examines the ground* Tiny paw prints?",
            "*adjusts detective coat* The mystery continues...",
            "*pulls out notepad* Making note of this location...",
            "*determined baby detective face* Wilson, I will find you!"
        ];
        
        const randomLine = generalDetectiveLines[Math.floor(Math.random() * generalDetectiveLines.length)];
        this.nav.showStatus(`🔍 ${randomLine}`, 'info');
        
        this.detectiveMode = true;
        setTimeout(() => {
            this.detectiveMode = false;
        }, 2000);
    }
    
    foundWilson() {
        this.humphreySettings.wilsonMissing = false;
        
        const celebrations = [
            "WILSON! *happy baby detective bounce*",
            "*tears of joy* I found my best friend!",
            "*hugs Wilson tight* Never leave me again!",
            "Case closed! *tips tiny hat proudly*",
            "*happy waddle dance* The detective agency wins!"
        ];
        
        const celebration = celebrations[Math.floor(Math.random() * celebrations.length)];
        this.nav.showStatus(`🎉 ${celebration}`, 'success');
        
        // Victory animation
        this.victoryCelebration();
    }
    
    victoryCelebration() {
        // Special victory state
        const originalSpeed = this.humphreySettings.walkSpeed;
        this.humphreySettings.walkSpeed = 1.5; // Happy zoomies!
        
        // Reset after celebration
        setTimeout(() => {
            this.humphreySettings.walkSpeed = originalSpeed;
        }, 10000);
    }
    
    isNearClue() {
        const room = this.nav.rooms[this.nav.player.room];
        
        for (const zone of room.zones || []) {
            if (zone.type.includes('wilson') || zone.type.includes('clue')) {
                const distance = Math.sqrt(
                    (this.nav.player.position.x - (zone.x + zone.width/2)) ** 2 +
                    (this.nav.player.position.y - (zone.y + zone.height/2)) ** 2
                );
                if (distance < 100) return true;
            }
        }
        return false;
    }
    
    checkDetectiveZones() {
        if (this.isNearClue() && !this.detectiveMode) {
            this.nav.showStatus("🔍 Humphrey senses a clue nearby! Press SPACE to investigate!", 'warning');
        }
    }
    
    updateDetectiveStatus() {
        const timeSinceLastInvestigation = this.lastInvestigation ? 
            performance.now() - this.lastInvestigation : 999999;
        
        // Humphrey gets determined if he hasn't found clues in a while
        if (timeSinceLastInvestigation > 30000) { // 30 seconds
            if (Math.random() < 0.001) { // Occasional determined comment
                const determinedLines = [
                    "*determined baby detective face* Wilson is counting on me!",
                    "*adjusts tiny hat* A real detective never gives up!",
                    "*pulls coat tighter* The case must be solved!"
                ];
                
                const line = determinedLines[Math.floor(Math.random() * determinedLines.length)];
                this.nav.showStatus(`💪 ${line}`, 'info');
            }
        }
    }
    
    startWilsonSearch() {
        // Initial detective briefing
        setTimeout(() => {
            this.nav.showStatus("👶🕵️ Detective Humphrey on the case! Wilson the teddy bear is missing!", 'info');
        }, 1000);
        
        setTimeout(() => {
            this.nav.showStatus("🧸 Help Humphrey find Wilson by investigating clues in each room!", 'info');
        }, 3000);
        
        setTimeout(() => {
            this.nav.showStatus("🔍 Use SPACE or E to investigate when you see clues!", 'info');
        }, 5000);
    }
    
    // Public API
    getCaseNotes() {
        return this.caseNotes;
    }
    
    getWilsonClueCount() {
        return this.wilsonClues;
    }
    
    isWilsonFound() {
        return !this.humphreySettings.wilsonMissing;
    }
    
    humphreyStatus() {
        return {
            mood: this.humphreySettings.mood,
            wilsonMissing: this.humphreySettings.wilsonMissing,
            cluesFound: this.wilsonClues,
            totalNotes: this.caseNotes.length,
            currentRoom: this.nav.player.room,
            detectiveMode: this.detectiveMode
        };
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HumphreyDetectiveExtensions;
} else if (typeof window !== 'undefined') {
    window.HumphreyDetectiveExtensions = HumphreyDetectiveExtensions;
}
