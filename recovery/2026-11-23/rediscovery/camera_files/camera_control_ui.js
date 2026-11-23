/**
 * Enhanced Control Room Camera System
 * Integrates with new camera management and video switching APIs
 */

class ControlRoomCameraSystem {
    constructor() {
        this.cameras = new Map();
        this.switcher = {
            inputs: new Map(),
            programInput: 0,
            previewInput: 0,
            state: 'idle',
            recordings: new Map()
        };
        
        this.wsConnection = null;
        this.updateInterval = null;
        this.lastUpdate = 0;
        
        this.init();
    }
    
    init() {
        this.createCameraUI();
        this.bindEvents();
        this.connectWebSocket();
        this.startPeriodicUpdate();
        this.loadInitialData();
    }
    
    // ═══════════════════════════════════════════════════════════════
    // UI CREATION
    // ═══════════════════════════════════════════════════════════════
    
    createCameraUI() {
        // Find existing stations or create new camera station
        let stationsBar = document.getElementById('stations-bar');
        if (stationsBar && !document.querySelector('[data-station="cameras"]')) {
            const cameraButton = document.createElement('button');
            cameraButton.className = 'ghost';
            cameraButton.setAttribute('data-station', 'cameras');
            cameraButton.textContent = 'Cameras';
            stationsBar.appendChild(cameraButton);
        }
        
        // Create camera station panel
        this.createCameraStation();
        
        // Create video switcher panel  
        this.createSwitcherPanel();
        
        // Create recording panel
        this.createRecordingPanel();
    }
    
    createCameraStation() {
        // Check if camera station already exists
        let cameraStation = document.getElementById('station-cameras');
        if (!cameraStation) {
            cameraStation = document.createElement('div');
            cameraStation.id = 'station-cameras';
            cameraStation.className = 'station hidden';
            
            const controlSection = document.querySelector('#view-control');
            if (controlSection) {
                controlSection.appendChild(cameraStation);
            }
        }
        
        cameraStation.innerHTML = `
            <div class="panel">
                <h3>📹 Camera Management</h3>
                <div class="camera-grid">
                    <div class="camera-sources" id="camera-sources">
                        <div class="loading">Loading cameras...</div>
                    </div>
                </div>
                <div class="camera-actions">
                    <button id="add-camera-btn" class="ghost">+ Add Camera</button>
                    <button id="sync-cameras-btn" class="ghost">🔄 Sync</button>
                    <button id="camera-monitoring-btn" class="ghost">Monitor: OFF</button>
                </div>
            </div>
            
            <div class="panel">
                <h3>🎛️ Video Switcher</h3>
                <div class="switcher-section">
                    <div class="switcher-status">
                        <div class="status-item">
                            <span>State:</span>
                            <span id="switcher-state" class="status-value">IDLE</span>
                        </div>
                        <div class="status-item">
                            <span>Program:</span>
                            <span id="program-input" class="status-value">None</span>
                        </div>
                        <div class="status-item">
                            <span>Preview:</span>
                            <span id="preview-input" class="status-value">None</span>
                        </div>
                    </div>
                    
                    <div class="switcher-inputs" id="switcher-inputs">
                        <div class="loading">Loading inputs...</div>
                    </div>
                    
                    <div class="switcher-controls">
                        <button id="transition-btn" class="primary" disabled>Take</button>
                        <select id="transition-type">
                            <option value="cut">Cut</option>
                            <option value="fade">Fade</option>
                            <option value="dissolve">Dissolve</option>
                        </select>
                        <input id="transition-duration" type="number" min="100" max="5000" value="1000" placeholder="Duration (ms)">
                    </div>
                </div>
            </div>
        `;
    }
    
    createSwitcherPanel() {
        // Enhanced switcher controls for existing director station
        const directorStation = document.getElementById('station-director');
        if (!directorStation) return;
        
        // Add camera switcher to vision mixer section
        const visionMixer = directorStation.querySelector('.panel h3');
        if (visionMixer && visionMixer.textContent === 'Vision Mixer') {
            const mixerPanel = visionMixer.parentElement;
            
            // Add camera input grid
            const inputGrid = document.createElement('div');
            inputGrid.className = 'camera-input-grid';
            inputGrid.innerHTML = `
                <div class="input-section">
                    <h4>Camera Inputs</h4>
                    <div class="input-grid" id="input-grid">
                        <!-- Camera inputs will be populated here -->
                    </div>
                </div>
            `;
            
            mixerPanel.appendChild(inputGrid);
        }
    }
    
    createRecordingPanel() {
        const recordingPanel = document.createElement('div');
        recordingPanel.className = 'panel';
        recordingPanel.innerHTML = `
            <h3>🎥 Recording Control</h3>
            <div class="recording-section">
                <div class="recording-status">
                    <div class="status-indicator" id="recording-indicator">
                        <span class="record-light"></span>
                        <span>Ready</span>
                    </div>
                </div>
                
                <div class="recording-controls">
                    <button id="start-recording-btn" class="primary">● Record</button>
                    <button id="stop-recording-btn" class="ghost" disabled>⏹ Stop</button>
                    <button id="stop-all-recordings-btn" class="ghost">⏹ Stop All</button>
                </div>
                
                <div class="recording-sessions" id="recording-sessions">
                    <h4>Active Recordings</h4>
                    <div class="session-list" id="session-list">
                        <em>No active recordings</em>
                    </div>
                </div>
            </div>
        `;
        
        const cameraStation = document.getElementById('station-cameras');
        if (cameraStation) {
            cameraStation.appendChild(recordingPanel);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════
    // EVENT BINDING
    // ═══════════════════════════════════════════════════════════════
    
    bindEvents() {
        // Camera management events
        document.getElementById('add-camera-btn')?.addEventListener('click', () => this.showAddCameraDialog());
        document.getElementById('sync-cameras-btn')?.addEventListener('click', () => this.syncCameras());
        document.getElementById('camera-monitoring-btn')?.addEventListener('click', () => this.toggleMonitoring());
        
        // Switcher events
        document.getElementById('transition-btn')?.addEventListener('click', () => this.executeTransition());
        
        // Recording events
        document.getElementById('start-recording-btn')?.addEventListener('click', () => this.startRecording());
        document.getElementById('stop-recording-btn')?.addEventListener('click', () => this.stopCurrentRecording());
        document.getElementById('stop-all-recordings-btn')?.addEventListener('click', () => this.stopAllRecordings());
        
        // Station switching
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-station="cameras"]')) {
                this.showCameraStation();
            }
        });
        
        // Keyboard shortcuts for switching
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            // Number keys 1-9 for camera switching
            if (e.key >= '1' && e.key <= '9') {
                const inputId = parseInt(e.key);
                if (e.shiftKey) {
                    this.setPreview(inputId);
                } else {
                    this.cutToInput(inputId);
                }
                e.preventDefault();
            }
            
            // Space for transition
            if (e.key === ' ' || e.key === 'Enter') {
                this.executeTransition();
                e.preventDefault();
            }
            
            // R for record
            if (e.key === 'r' && e.ctrlKey) {
                this.startRecording();
                e.preventDefault();
            }
        });
    }
    
    showCameraStation() {
        // Hide other stations
        document.querySelectorAll('.station').forEach(station => {
            station.classList.add('hidden');
        });
        
        // Show camera station
        const cameraStation = document.getElementById('station-cameras');
        if (cameraStation) {
            cameraStation.classList.remove('hidden');
        }
    }
    
    // ═══════════════════════════════════════════════════════════════
    // WEBSOCKET CONNECTION
    // ═══════════════════════════════════════════════════════════════
    
    connectWebSocket() {
        const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/control/${window.userId || 'default'}`;
        
        try {
            this.wsConnection = new WebSocket(wsUrl);
            
            this.wsConnection.onopen = () => {
                console.log('Camera WebSocket connected');
                this.requestCameraStatus();
            };
            
            this.wsConnection.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.wsConnection.onclose = () => {
                console.log('Camera WebSocket disconnected, reconnecting...');
                setTimeout(() => this.connectWebSocket(), 5000);
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
        }
    }
    
    handleWebSocketMessage(data) {
        if (data.category === 'camera') {
            switch (data.type) {
                case 'switcher_update':
                    this.updateSwitcherStatus(data.data);
                    break;
                case 'recording_update':
                    this.updateRecordingStatus(data.data);
                    break;
                case 'camera_status':
                    this.updateCameraStatus(data.data);
                    break;
            }
        }
    }
    
    sendWebSocketMessage(type, data = {}) {
        if (this.wsConnection && this.wsConnection.readyState === WebSocket.OPEN) {
            this.wsConnection.send(JSON.stringify({
                category: 'camera',
                type: type,
                data: data
            }));
        }
    }
    
    requestCameraStatus() {
        this.sendWebSocketMessage('camera_status_request');
    }
    
    // ═══════════════════════════════════════════════════════════════
    // API COMMUNICATION
    // ═══════════════════════════════════════════════════════════════
    
    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(`/api/cameras${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API call failed: ${response.status}`);
            }
            
            return await response.json();
            
        } catch (error) {
            console.error(`API call failed for ${endpoint}:`, error);
            this.showStatus(`API Error: ${error.message}`, 'error');
            throw error;
        }
    }
    
    async loadInitialData() {
        try {
            // Load camera and switcher data
            const data = await this.apiCall('/data');
            
            if (data.cameras) {
                this.updateCameraList(data.cameras.sources);
            }
            
            if (data.switcher) {
                this.updateSwitcherInputs(data.switcher.inputs);
                this.updateSwitcherStatus(data.switcher.status);
                this.updateRecordingList(data.switcher.recordings);
            }
            
        } catch (error) {
            console.error('Failed to load initial camera data:', error);
        }
    }
    
    startPeriodicUpdate() {
        this.updateInterval = setInterval(async () => {
            try {
                await this.loadInitialData();
            } catch (error) {
                console.error('Periodic update failed:', error);
            }
        }, 5000); // Update every 5 seconds
    }
    
    // ═══════════════════════════════════════════════════════════════
    // CAMERA OPERATIONS
    // ═══════════════════════════════════════════════════════════════
    
    async syncCameras() {
        try {
            await this.apiCall('/sync', { method: 'POST' });
            this.showStatus('Cameras synchronized', 'success');
            await this.loadInitialData();
        } catch (error) {
            this.showStatus('Failed to sync cameras', 'error');
        }
    }
    
    async toggleMonitoring() {
        try {
            const btn = document.getElementById('camera-monitoring-btn');
            const isOn = btn.textContent.includes('ON');
            
            if (isOn) {
                await this.apiCall('/monitoring/stop', { method: 'POST' });
                btn.textContent = 'Monitor: OFF';
            } else {
                await this.apiCall('/monitoring/start', { method: 'POST' });
                btn.textContent = 'Monitor: ON';
            }
            
        } catch (error) {
            this.showStatus('Failed to toggle monitoring', 'error');
        }
    }
    
    updateCameraList(sources) {
        const container = document.getElementById('camera-sources');
        if (!container) return;
        
        this.cameras.clear();
        
        if (!sources || sources.length === 0) {
            container.innerHTML = '<div class="no-cameras">No cameras available</div>';
            return;
        }
        
        container.innerHTML = sources.map(source => {
            this.cameras.set(source.source_id, source);
            
            return `
                <div class="camera-source" data-source-id="${source.source_id}">
                    <div class="camera-header">
                        <span class="camera-name">${source.name}</span>
                        <span class="camera-transport ${source.transport}">${source.transport.toUpperCase()}</span>
                    </div>
                    <div class="camera-info">
                        <div class="camera-location">${source.location}</div>
                        <div class="camera-resolution">${source.resolution}@${source.framerate}fps</div>
                    </div>
                    <div class="camera-status">
                        <span class="status-indicator offline">●</span>
                        <span class="status-text">Checking...</span>
                    </div>
                    <div class="camera-actions">
                        <button class="ghost small" onclick="cameraSystem.editCamera('${source.source_id}')">Edit</button>
                        <button class="ghost small danger" onclick="cameraSystem.deleteCamera('${source.source_id}')">Delete</button>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    // ═══════════════════════════════════════════════════════════════
    // SWITCHER OPERATIONS
    // ═══════════════════════════════════════════════════════════════
    
    async cutToInput(inputId) {
        try {
            await this.apiCall(`/switcher/cut/${inputId}`, { method: 'POST' });
            this.sendWebSocketMessage('camera_cut', { input_id: inputId });
            this.showStatus(`Cut to input ${inputId}`, 'success');
        } catch (error) {
            this.showStatus(`Failed to cut to input ${inputId}`, 'error');
        }
    }
    
    async setPreview(inputId) {
        try {
            await this.apiCall(`/switcher/preview/${inputId}`, { method: 'POST' });
            this.sendWebSocketMessage('camera_preview', { input_id: inputId });
            this.showStatus(`Preview set to input ${inputId}`, 'success');
        } catch (error) {
            this.showStatus(`Failed to set preview ${inputId}`, 'error');
        }
    }
    
    async executeTransition() {
        try {
            const transitionType = document.getElementById('transition-type')?.value || 'cut';
            const duration = parseInt(document.getElementById('transition-duration')?.value) || 1000;
            
            await this.apiCall('/switcher/transition', {
                method: 'POST',
                body: JSON.stringify({
                    transition_type: transitionType,
                    duration_ms: duration
                })
            });
            
            this.showStatus(`Executed ${transitionType} transition`, 'success');
            
        } catch (error) {
            this.showStatus('Failed to execute transition', 'error');
        }
    }
    
    updateSwitcherInputs(inputs) {
        const container = document.getElementById('switcher-inputs');
        const gridContainer = document.getElementById('input-grid');
        
        if (!inputs || inputs.length === 0) {
            if (container) container.innerHTML = '<div class="no-inputs">No inputs available</div>';
            return;
        }
        
        this.switcher.inputs.clear();
        
        const inputHtml = inputs.map(input => {
            this.switcher.inputs.set(input.id, input);
            
            const isProgram = input.active;
            const isPreview = input.preview;
            const isRecording = input.recording;
            
            return `
                <div class="switcher-input ${isProgram ? 'program' : ''} ${isPreview ? 'preview' : ''}" 
                     data-input-id="${input.id}">
                    <div class="input-header">
                        <span class="input-number">${input.id}</span>
                        <span class="input-name">${input.name}</span>
                    </div>
                    <div class="input-preview">
                        <div class="preview-placeholder">
                            ${input.type.toUpperCase()}
                        </div>
                    </div>
                    <div class="input-controls">
                        <button class="input-btn preview-btn" onclick="cameraSystem.setPreview(${input.id})">PVW</button>
                        <button class="input-btn program-btn" onclick="cameraSystem.cutToInput(${input.id})">PGM</button>
                    </div>
                    <div class="input-status">
                        ${isRecording ? '<span class="recording-indicator">● REC</span>' : ''}
                        ${!input.video_enabled ? '<span class="disabled-indicator">NO VIDEO</span>' : ''}
                        ${!input.audio_enabled ? '<span class="disabled-indicator">NO AUDIO</span>' : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        if (container) container.innerHTML = inputHtml;
        if (gridContainer) gridContainer.innerHTML = inputHtml;
    }
    
    updateSwitcherStatus(status) {
        if (!status) return;
        
        // Update status displays
        const stateEl = document.getElementById('switcher-state');
        const programEl = document.getElementById('program-input');
        const previewEl = document.getElementById('preview-input');
        
        if (stateEl) stateEl.textContent = status.state.toUpperCase();
        if (programEl) programEl.textContent = status.program_input || 'None';
        if (previewEl) previewEl.textContent = status.preview_input || 'None';
        
        // Update transition button
        const transitionBtn = document.getElementById('transition-btn');
        if (transitionBtn) {
            transitionBtn.disabled = !status.preview_input || status.preview_input === status.program_input;
        }
        
        // Store current status
        Object.assign(this.switcher, status);
    }
    
    // ═══════════════════════════════════════════════════════════════
    // RECORDING OPERATIONS
    // ═══════════════════════════════════════════════════════════════
    
    async startRecording() {
        try {
            const result = await this.apiCall('/recording/start', {
                method: 'POST',
                body: JSON.stringify({
                    quality: 'high',
                    format: 'mp4'
                })
            });
            
            this.sendWebSocketMessage('recording_start', result);
            this.showStatus('Recording started', 'success');
            
            // Update UI
            const startBtn = document.getElementById('start-recording-btn');
            const stopBtn = document.getElementById('stop-recording-btn');
            const indicator = document.getElementById('recording-indicator');
            
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
            if (indicator) {
                indicator.innerHTML = '<span class="record-light active"></span><span>Recording</span>';
            }
            
        } catch (error) {
            this.showStatus('Failed to start recording', 'error');
        }
    }
    
    async stopCurrentRecording() {
        try {
            // Find active recording
            const activeRecording = Array.from(this.switcher.recordings.values())
                .find(r => r.status === 'recording');
            
            if (!activeRecording) {
                this.showStatus('No active recording to stop', 'warning');
                return;
            }
            
            await this.apiCall(`/recording/stop/${activeRecording.session_id}`, { method: 'POST' });
            this.sendWebSocketMessage('recording_stop', { session_id: activeRecording.session_id });
            this.showStatus('Recording stopped', 'success');
            
        } catch (error) {
            this.showStatus('Failed to stop recording', 'error');
        }
    }
    
    async stopAllRecordings() {
        try {
            await this.apiCall('/recording/stop-all', { method: 'POST' });
            this.showStatus('All recordings stopped', 'success');
        } catch (error) {
            this.showStatus('Failed to stop all recordings', 'error');
        }
    }
    
    updateRecordingList(recordings) {
        const container = document.getElementById('session-list');
        if (!container) return;
        
        this.switcher.recordings.clear();
        
        if (!recordings || recordings.length === 0) {
            container.innerHTML = '<em>No active recordings</em>';
            return;
        }
        
        const activeRecordings = recordings.filter(r => r.status === 'recording');
        
        if (activeRecordings.length === 0) {
            container.innerHTML = '<em>No active recordings</em>';
            
            // Reset recording UI
            const startBtn = document.getElementById('start-recording-btn');
            const stopBtn = document.getElementById('stop-recording-btn');
            const indicator = document.getElementById('recording-indicator');
            
            if (startBtn) startBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = true;
            if (indicator) {
                indicator.innerHTML = '<span class="record-light"></span><span>Ready</span>';
            }
            
            return;
        }
        
        container.innerHTML = activeRecordings.map(recording => {
            this.switcher.recordings.set(recording.session_id, recording);
            
            return `
                <div class="recording-session" data-session-id="${recording.session_id}">
                    <div class="session-info">
                        <span class="session-name">${recording.filename}</span>
                        <span class="session-duration">${this.formatDuration(recording.duration_seconds)}</span>
                    </div>
                    <div class="session-controls">
                        <button class="ghost small" onclick="cameraSystem.stopRecording('${recording.session_id}')">Stop</button>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    async stopRecording(sessionId) {
        try {
            await this.apiCall(`/recording/stop/${sessionId}`, { method: 'POST' });
            this.showStatus('Recording stopped', 'success');
        } catch (error) {
            this.showStatus('Failed to stop recording', 'error');
        }
    }
    
    // ═══════════════════════════════════════════════════════════════
    // UTILITY METHODS
    // ═══════════════════════════════════════════════════════════════
    
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    showStatus(message, type = 'info') {
        // Create or update status toast
        let toast = document.querySelector('.camera-status-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'camera-status-toast';
            document.body.appendChild(toast);
        }
        
        toast.textContent = message;
        toast.className = `camera-status-toast ${type} show`;
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
    
    showAddCameraDialog() {
        // TODO: Implement add camera dialog
        this.showStatus('Add camera dialog not implemented yet', 'info');
    }
    
    editCamera(sourceId) {
        // TODO: Implement edit camera dialog
        this.showStatus(`Edit camera ${sourceId} not implemented yet`, 'info');
    }
    
    async deleteCamera(sourceId) {
        if (!confirm('Are you sure you want to delete this camera?')) return;
        
        try {
            await this.apiCall(`/${sourceId}`, { method: 'DELETE' });
            this.showStatus('Camera deleted', 'success');
            await this.loadInitialData();
        } catch (error) {
            this.showStatus('Failed to delete camera', 'error');
        }
    }
    
    cleanup() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        if (this.wsConnection) {
            this.wsConnection.close();
        }
    }
}

// Initialize camera system when page loads
let cameraSystem = null;

document.addEventListener('DOMContentLoaded', () => {
    cameraSystem = new ControlRoomCameraSystem();
});

// Export for global access
if (typeof window !== 'undefined') {
    window.cameraSystem = cameraSystem;
}
