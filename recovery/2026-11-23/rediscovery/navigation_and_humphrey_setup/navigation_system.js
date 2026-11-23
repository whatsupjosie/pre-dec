/**
 * PubCast 3D Navigation System
 * Smooth movement with multiple camera modes and room transitions
 * Build the building first approach - mechanics before decoration
 */

class PubCastNavigation {
    constructor(options = {}) {
        this.container = options.container || document.body;
        this.websocket = options.websocket || null;
        
        // Movement settings
        this.movement = {
            speed: options.walkSpeed || 1.0,
            turnSpeed: options.turnSensitivity || 1.0,
            acceleration: 0.15,
            deceleration: 0.12,
            currentVelocity: { x: 0, y: 0 },
            targetVelocity: { x: 0, y: 0 }
        };
        
        // Camera settings  
        this.camera = {
            mode: 'fixed', // 'fixed' or 'third_person'
            position: { x: 0, y: 0, z: 5 },
            target: { x: 0, y: 0, z: 0 },
            distance: 4.5, // for third person
            height: 1.8,   // for third person
            angle: 0,      // rotation angle
            smooth: true,
            followSpeed: 0.08
        };
        
        // Player state
        this.player = {
            position: { x: 0, y: 0, z: 0 },
            rotation: 0,
            room: 'dressing_room',
            moving: false,
            canMove: true
        };
        
        // Room definitions with camera presets
        this.rooms = this.initializeRooms();
        
        // Input state
        this.keys = {
            w: false, a: false, s: false, d: false,
            shift: false, space: false
        };
        
        // Canvas and rendering
        this.canvas = null;
        this.ctx = null;
        this.isRendering = false;
        
        this.init();
    }
    
    init() {
        this.createCanvas();
        this.bindControls();
        this.bindKeyboard();
        this.startRenderLoop();
        this.loadRoom(this.player.room);
        
        // Initialize at dressing room spawn point
        this.setPlayerPosition(this.rooms[this.player.room].spawn);
    }
    
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'navigation-canvas';
        this.canvas.width = 1200;
        this.canvas.height = 800;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.background = 'linear-gradient(135deg, #0f1419 0%, #1a1a2e 50%, #16213e 100%)';
        
        this.ctx = this.canvas.getContext('2d');
        this.container.appendChild(this.canvas);
        
        // Handle canvas resize
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }
    
    initializeRooms() {
        return {
            dressing_room: {
                name: 'Dressing Room',
                bounds: { x: 0, y: 0, width: 800, height: 600 },
                spawn: { x: 400, y: 300, z: 0 },
                camera: { mode: 'fixed', position: { x: 400, y: 300, z: 6 } },
                exits: [
                    { zone: { x: 750, y: 250, width: 50, height: 100 }, 
                      target: 'green_room', spawn: { x: 50, y: 300, z: 0 } }
                ],
                zones: [
                    { type: 'wardrobe', x: 100, y: 100, width: 150, height: 80, 
                      action: 'open_wardrobe' },
                    { type: 'mirror', x: 300, y: 50, width: 200, height: 100, 
                      action: 'avatar_customization' },
                    { type: 'desk', x: 600, y: 400, width: 120, height: 80, 
                      action: 'settings_panel' }
                ]
            },
            
            green_room: {
                name: 'Green Room',
                bounds: { x: 0, y: 0, width: 1000, height: 700 },
                spawn: { x: 100, y: 350, z: 0 },
                camera: { mode: 'fixed', position: { x: 500, y: 350, z: 7 } },
                exits: [
                    { zone: { x: 0, y: 300, width: 50, height: 100 }, 
                      target: 'dressing_room', spawn: { x: 750, y: 300, z: 0 } },
                    { zone: { x: 950, y: 200, width: 50, height: 150 }, 
                      target: 'studio', spawn: { x: 50, y: 400, z: 0 } },
                    { zone: { x: 450, y: 650, width: 100, height: 50 }, 
                      target: 'pub', spawn: { x: 400, y: 50, z: 0 } }
                ],
                zones: [
                    { type: 'couch', x: 200, y: 300, width: 200, height: 100, 
                      action: 'sit_relax' },
                    { type: 'window', x: 700, y: 100, width: 200, height: 150, 
                      action: 'view_studio' },
                    { type: 'coffee', x: 400, y: 500, width: 80, height: 80, 
                      action: 'get_coffee' }
                ]
            },
            
            studio: {
                name: 'Studio',
                bounds: { x: 0, y: 0, width: 1200, height: 800 },
                spawn: { x: 100, y: 400, z: 0 },
                camera: { mode: 'third_person', distance: 5.5, height: 2.0 },
                exits: [
                    { zone: { x: 0, y: 350, width: 50, height: 100 }, 
                      target: 'green_room', spawn: { x: 950, y: 275, z: 0 } },
                    { zone: { x: 1150, y: 300, width: 50, height: 200 }, 
                      target: 'control_room', spawn: { x: 50, y: 400, z: 0 } }
                ],
                zones: [
                    { type: 'stage', x: 400, y: 200, width: 400, height: 300, 
                      action: 'enter_stage' },
                    { type: 'camera1', x: 200, y: 600, width: 100, height: 80, 
                      action: 'operate_camera' },
                    { type: 'lighting', x: 800, y: 600, width: 120, height: 80, 
                      action: 'adjust_lighting' }
                ]
            },
            
            control_room: {
                name: 'Control Room',
                bounds: { x: 0, y: 0, width: 1100, height: 700 },
                spawn: { x: 100, y: 400, z: 0 },
                camera: { mode: 'fixed', position: { x: 550, y: 350, z: 8 } },
                exits: [
                    { zone: { x: 0, y: 350, width: 50, height: 100 }, 
                      target: 'studio', spawn: { x: 1150, y: 400, z: 0 } }
                ],
                zones: [
                    { type: 'director_station', x: 400, y: 300, width: 300, height: 150, 
                      action: 'director_controls' },
                    { type: 'audio_board', x: 100, y: 500, width: 200, height: 100, 
                      action: 'audio_mixing' },
                    { type: 'video_switcher', x: 700, y: 500, width: 200, height: 100, 
                      action: 'video_switching' }
                ]
            },
            
            pub: {
                name: 'The Pub',
                bounds: { x: 0, y: 0, width: 1000, height: 600 },
                spawn: { x: 400, y: 100, z: 0 },
                camera: { mode: 'third_person', distance: 4.0, height: 1.5 },
                exits: [
                    { zone: { x: 350, y: 0, width: 100, height: 50 }, 
                      target: 'green_room', spawn: { x: 500, y: 650, z: 0 } }
                ],
                zones: [
                    { type: 'bar', x: 200, y: 400, width: 300, height: 100, 
                      action: 'order_drink' },
                    { type: 'games', x: 600, y: 200, width: 150, height: 150, 
                      action: 'play_games' },
                    { type: 'jukebox', x: 50, y: 200, width: 80, height: 120, 
                      action: 'play_music' }
                ]
            }
        };
    }
    
    // Keyboard Controls
    bindKeyboard() {
        document.addEventListener('keydown', (e) => this.onKeyDown(e));
        document.addEventListener('keyup', (e) => this.onKeyUp(e));
        
        // Prevent default browser behavior for WASD
        document.addEventListener('keydown', (e) => {
            if (['w', 'a', 's', 'd', ' '].includes(e.key.toLowerCase())) {
                e.preventDefault();
            }
        });
    }
    
    onKeyDown(e) {
        const key = e.key.toLowerCase();
        
        // Movement keys
        if (key in this.keys) {
            this.keys[key] = true;
        }
        
        // Camera toggle
        if (key === 'c') {
            this.toggleCameraMode();
        }
        
        // Speed boost
        if (key === 'shift') {
            this.keys.shift = true;
        }
        
        // Interaction
        if (key === ' ' || key === 'e') {
            this.interact();
        }
        
        // Room quick travel (for debugging)
        if (e.ctrlKey) {
            const roomKeys = { '1': 'dressing_room', '2': 'green_room', '3': 'studio', '4': 'control_room', '5': 'pub' };
            if (roomKeys[key]) {
                this.teleportToRoom(roomKeys[key]);
            }
        }
    }
    
    onKeyUp(e) {
        const key = e.key.toLowerCase();
        if (key in this.keys) {
            this.keys[key] = false;
        }
    }
    
    // Movement System
    updateMovement(deltaTime) {
        if (!this.player.canMove) return;
        
        // Calculate target velocity based on input
        const speed = this.movement.speed * (this.keys.shift ? 1.8 : 1.0);
        
        this.movement.targetVelocity.x = 0;
        this.movement.targetVelocity.y = 0;
        
        // Screen-relative movement (bottom of screen = down, top = up)
        if (this.keys.w) this.movement.targetVelocity.y = -speed; // Up
        if (this.keys.s) this.movement.targetVelocity.y = speed;  // Down
        if (this.keys.a) this.movement.targetVelocity.x = -speed; // Left
        if (this.keys.d) this.movement.targetVelocity.x = speed;  // Right
        
        // Normalize diagonal movement
        if (this.movement.targetVelocity.x !== 0 && this.movement.targetVelocity.y !== 0) {
            const length = Math.sqrt(this.movement.targetVelocity.x ** 2 + this.movement.targetVelocity.y ** 2);
            this.movement.targetVelocity.x = (this.movement.targetVelocity.x / length) * speed;
            this.movement.targetVelocity.y = (this.movement.targetVelocity.y / length) * speed;
        }
        
        // Smooth acceleration/deceleration
        const accel = this.movement.targetVelocity.x !== 0 || this.movement.targetVelocity.y !== 0 
                     ? this.movement.acceleration : this.movement.deceleration;
        
        this.movement.currentVelocity.x = this.lerp(this.movement.currentVelocity.x, this.movement.targetVelocity.x, accel);
        this.movement.currentVelocity.y = this.lerp(this.movement.currentVelocity.y, this.movement.targetVelocity.y, accel);
        
        // Apply movement
        const newPosition = {
            x: this.player.position.x + this.movement.currentVelocity.x * deltaTime * 60,
            y: this.player.position.y + this.movement.currentVelocity.y * deltaTime * 60,
            z: this.player.position.z
        };
        
        // Check bounds and collision
        if (this.isValidPosition(newPosition)) {
            this.setPlayerPosition(newPosition);
            this.player.moving = Math.abs(this.movement.currentVelocity.x) > 0.1 || Math.abs(this.movement.currentVelocity.y) > 0.1;
            
            // Update rotation based on movement direction
            if (this.player.moving) {
                this.player.rotation = Math.atan2(this.movement.currentVelocity.y, this.movement.currentVelocity.x);
            }
        }
        
        // Check for room exits and zone interactions
        this.checkExits();
        this.checkZones();
    }
    
    // Camera System
    updateCamera(deltaTime) {
        const room = this.rooms[this.player.room];
        
        if (this.camera.mode === 'fixed') {
            // Fixed camera - use room's predefined position
            if (room.camera && room.camera.position) {
                this.camera.position = { ...room.camera.position };
                this.camera.target = { x: this.player.position.x, y: this.player.position.y, z: 0 };
            }
        } else if (this.camera.mode === 'third_person') {
            // Third person over-shoulder camera
            const distance = room.camera?.distance || this.camera.distance;
            const height = room.camera?.height || this.camera.height;
            
            // Calculate camera position behind and above player
            const angle = this.player.rotation + Math.PI; // Behind player
            const targetCameraX = this.player.position.x + Math.cos(angle) * distance;
            const targetCameraY = this.player.position.y + Math.sin(angle) * distance;
            const targetCameraZ = this.player.position.z + height;
            
            // Smooth camera following
            if (this.camera.smooth) {
                this.camera.position.x = this.lerp(this.camera.position.x, targetCameraX, this.camera.followSpeed);
                this.camera.position.y = this.lerp(this.camera.position.y, targetCameraY, this.camera.followSpeed);
                this.camera.position.z = this.lerp(this.camera.position.z, targetCameraZ, this.camera.followSpeed);
            } else {
                this.camera.position.x = targetCameraX;
                this.camera.position.y = targetCameraY;
                this.camera.position.z = targetCameraZ;
            }
            
            this.camera.target = { ...this.player.position };
        }
    }
    
    toggleCameraMode() {
        this.camera.mode = this.camera.mode === 'fixed' ? 'third_person' : 'fixed';
        this.showStatus(`Camera: ${this.camera.mode.replace('_', ' ')}`, 'info');
        
        // Smooth transition when switching modes
        this.updateCamera(0);
    }
    
    // Room Management
    loadRoom(roomId) {
        if (!this.rooms[roomId]) return false;
        
        this.player.room = roomId;
        const room = this.rooms[roomId];
        
        // Set camera mode for room
        if (room.camera) {
            if (room.camera.mode) {
                this.camera.mode = room.camera.mode;
            }
        }
        
        // Update camera immediately
        this.updateCamera(0);
        
        this.showStatus(`Entered ${room.name}`, 'success');
        
        // Notify via WebSocket
        if (this.websocket) {
            this.sendWebSocketMessage({
                type: 'room_changed',
                room: roomId,
                position: this.player.position
            });
        }
        
        return true;
    }
    
    teleportToRoom(roomId) {
        if (this.loadRoom(roomId)) {
            this.setPlayerPosition(this.rooms[roomId].spawn);
        }
    }
    
    // Collision and Interaction
    isValidPosition(position) {
        const room = this.rooms[this.player.room];
        const bounds = room.bounds;
        
        // Simple bounds checking
        return position.x >= 20 && position.x <= bounds.width - 20 &&
               position.y >= 20 && position.y <= bounds.height - 20;
    }
    
    checkExits() {
        const room = this.rooms[this.player.room];
        
        for (const exit of room.exits || []) {
            if (this.isInZone(this.player.position, exit.zone)) {
                this.teleportToRoom(exit.target);
                this.setPlayerPosition(exit.spawn);
                break;
            }
        }
    }
    
    checkZones() {
        const room = this.rooms[this.player.room];
        
        for (const zone of room.zones || []) {
            if (this.isInZone(this.player.position, zone)) {
                this.showInteractionHint(zone);
                break;
            }
        }
    }
    
    isInZone(position, zone) {
        return position.x >= zone.x && position.x <= zone.x + zone.width &&
               position.y >= zone.y && position.y <= zone.y + zone.height;
    }
    
    interact() {
        const room = this.rooms[this.player.room];
        
        for (const zone of room.zones || []) {
            if (this.isInZone(this.player.position, zone)) {
                this.triggerAction(zone.action, zone);
                break;
            }
        }
    }
    
    triggerAction(action, zone) {
        this.showStatus(`Action: ${action}`, 'info');
        
        // Emit event for UI systems to handle
        document.dispatchEvent(new CustomEvent('navigation-action', {
            detail: { action, zone, room: this.player.room, position: this.player.position }
        }));
        
        // WebSocket notification
        if (this.websocket) {
            this.sendWebSocketMessage({
                type: 'player_action',
                action: action,
                zone: zone,
                position: this.player.position
            });
        }
    }
    
    // Rendering System
    startRenderLoop() {
        if (this.isRendering) return;
        this.isRendering = true;
        
        let lastTime = performance.now();
        const render = (currentTime) => {
            if (!this.isRendering) return;
            
            const deltaTime = (currentTime - lastTime) / 1000;
            lastTime = currentTime;
            
            this.update(deltaTime);
            this.draw();
            
            requestAnimationFrame(render);
        };
        
        requestAnimationFrame(render);
    }
    
    update(deltaTime) {
        this.updateMovement(deltaTime);
        this.updateCamera(deltaTime);
    }
    
    draw() {
        const ctx = this.ctx;
        const canvas = this.canvas;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Set up camera transform
        ctx.save();
        this.applyCameraTransform();
        
        // Draw room
        this.drawRoom();
        
        // Draw player
        this.drawPlayer();
        
        // Draw zones (debug)
        if (this.debugMode) {
            this.drawZones();
        }
        
        ctx.restore();
        
        // Draw UI overlays
        this.drawUI();
    }
    
    applyCameraTransform() {
        const ctx = this.ctx;
        const canvas = this.canvas;
        
        // Center view on camera target
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        
        // Apply camera offset based on mode
        if (this.camera.mode === 'fixed') {
            ctx.translate(centerX - this.camera.position.x, centerY - this.camera.position.y);
        } else {
            ctx.translate(centerX - this.player.position.x, centerY - this.player.position.y);
        }
        
        // Apply zoom based on camera distance
        const zoom = Math.max(0.5, Math.min(2.0, 8.0 / (this.camera.position.z || 6)));
        ctx.scale(zoom, zoom);
    }
    
    drawRoom() {
        const room = this.rooms[this.player.room];
        const bounds = room.bounds;
        const ctx = this.ctx;
        
        // Room background
        ctx.fillStyle = 'rgba(26, 26, 46, 0.8)';
        ctx.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
        
        // Room border
        ctx.strokeStyle = 'rgba(0, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.strokeRect(bounds.x, bounds.y, bounds.width, bounds.height);
        
        // Draw zones as simple rectangles
        for (const zone of room.zones || []) {
            ctx.fillStyle = this.getZoneColor(zone.type);
            ctx.fillRect(zone.x, zone.y, zone.width, zone.height);
            
            // Zone labels
            ctx.fillStyle = '#ffffff';
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(zone.type, zone.x + zone.width/2, zone.y + zone.height/2);
        }
        
        // Draw exits
        for (const exit of room.exits || []) {
            ctx.fillStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.fillRect(exit.zone.x, exit.zone.y, exit.zone.width, exit.zone.height);
            
            ctx.fillStyle = '#ffd700';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('→ ' + exit.target, exit.zone.x + exit.zone.width/2, exit.zone.y + exit.zone.height/2);
        }
    }
    
    drawPlayer() {
        const ctx = this.ctx;
        const pos = this.player.position;
        
        ctx.save();
        ctx.translate(pos.x, pos.y);
        ctx.rotate(this.player.rotation);
        
        // Player body (simple circle for now)
        ctx.fillStyle = this.player.moving ? '#00ffff' : '#0099cc';
        ctx.beginPath();
        ctx.arc(0, 0, 15, 0, Math.PI * 2);
        ctx.fill();
        
        // Direction indicator
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(10, 0);
        ctx.lineTo(20, 0);
        ctx.stroke();
        
        ctx.restore();
    }
    
    drawUI() {
        const ctx = this.ctx;
        const canvas = this.canvas;
        
        // Room info
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(10, 10, 250, 80);
        
        ctx.fillStyle = '#00ffff';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`Room: ${this.rooms[this.player.room].name}`, 20, 30);
        ctx.fillText(`Camera: ${this.camera.mode.replace('_', ' ')}`, 20, 50);
        ctx.fillText(`Position: ${Math.round(this.player.position.x)}, ${Math.round(this.player.position.y)}`, 20, 70);
        
        // Controls help
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(canvas.width - 200, 10, 190, 120);
        
        ctx.fillStyle = '#ffffff';
        ctx.font = '12px sans-serif';
        ctx.fillText('Controls:', canvas.width - 190, 30);
        ctx.fillText('WASD - Move', canvas.width - 190, 50);
        ctx.fillText('Shift - Run', canvas.width - 190, 65);
        ctx.fillText('C - Toggle Camera', canvas.width - 190, 80);
        ctx.fillText('Space/E - Interact', canvas.width - 190, 95);
        ctx.fillText('Ctrl+1-5 - Quick Travel', canvas.width - 190, 110);
    }
    
    // Utility Methods
    lerp(a, b, factor) {
        return a + (b - a) * factor;
    }
    
    setPlayerPosition(position) {
        this.player.position = { ...position };
    }
    
    getZoneColor(type) {
        const colors = {
            wardrobe: 'rgba(255, 100, 200, 0.4)',
            mirror: 'rgba(200, 200, 255, 0.4)',
            desk: 'rgba(150, 100, 50, 0.4)',
            couch: 'rgba(100, 200, 100, 0.4)',
            window: 'rgba(255, 255, 100, 0.4)',
            coffee: 'rgba(139, 69, 19, 0.4)',
            stage: 'rgba(255, 50, 50, 0.4)',
            camera1: 'rgba(50, 255, 50, 0.4)',
            lighting: 'rgba(255, 255, 50, 0.4)',
            director_station: 'rgba(100, 100, 255, 0.4)',
            audio_board: 'rgba(255, 150, 50, 0.4)',
            video_switcher: 'rgba(50, 255, 255, 0.4)',
            bar: 'rgba(139, 69, 19, 0.4)',
            games: 'rgba(255, 100, 255, 0.4)',
            jukebox: 'rgba(100, 255, 100, 0.4)'
        };
        return colors[type] || 'rgba(128, 128, 128, 0.4)';
    }
    
    showStatus(message, type = 'info') {
        // Integration point with existing status system
        console.log(`Navigation: ${message}`);
        
        // Emit event for other systems
        document.dispatchEvent(new CustomEvent('navigation-status', {
            detail: { message, type }
        }));
    }
    
    showInteractionHint(zone) {
        // Show interaction prompt
        const hint = `Press SPACE or E to ${zone.action.replace('_', ' ')}`;
        this.showStatus(hint, 'info');
    }
    
    sendWebSocketMessage(message) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        }
    }
    
    // Public API
    setWalkSpeed(speed) {
        this.movement.speed = Math.max(0.1, Math.min(3.0, speed));
    }
    
    setTurnSensitivity(sensitivity) {
        this.movement.turnSpeed = Math.max(0.2, Math.min(2.5, sensitivity));
    }
    
    setCameraMode(mode) {
        if (['fixed', 'third_person'].includes(mode)) {
            this.camera.mode = mode;
            this.updateCamera(0);
        }
    }
    
    getCurrentRoom() {
        return this.player.room;
    }
    
    getPlayerPosition() {
        return { ...this.player.position };
    }
    
    destroy() {
        this.isRendering = false;
        document.removeEventListener('keydown', this.onKeyDown);
        document.removeEventListener('keyup', this.onKeyUp);
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PubCastNavigation;
} else if (typeof window !== 'undefined') {
    window.PubCastNavigation = PubCastNavigation;
}
