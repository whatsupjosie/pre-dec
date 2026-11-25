// ========================================
// PUBCAST DRESSING ROOM - COMPLETE SYSTEM
// Three Hotspots + Functional Typewriter
// ========================================

class DressingRoomSystem {
    constructor() {
        // Views
        this.roomView = document.getElementById('room-view');
        this.typewriterView = document.getElementById('typewriter-view');
        this.stageView = document.getElementById('stage-view');
        this.vanityView = document.getElementById('vanity-view');
        
        // Typewriter elements
        this.paperContent = document.getElementById('paper-content');
        this.docTitle = document.getElementById('doc-title');
        
        // Audio
        this.audioKeystroke = document.getElementById('audio-keystroke');
        this.audioDing = document.getElementById('audio-ding');
        this.audioReturn = document.getElementById('audio-return');
        
        // Document state
        this.currentDocument = {
            title: 'Untitled Document',
            content: '',
            category: 'general',
            lastModified: new Date().toISOString()
        };
        
        // Typing state
        this.charactersPerLine = 70;
        this.currentLinePosition = 0;
        
        // User ID
        this.userId = null;
        
        this.init();
    }
    
    async init() {
        await this.getUserId();
        this.setupHotspots();
        this.setupTypewriterControls();
        this.setupKeyboardInput();
        this.setupMenuSystem();
        this.setupModals();
        this.loadAutoSave();
    }
    
    // ========================================
    // USER MANAGEMENT
    // ========================================
    
    async getUserId() {
        try {
            const response = await fetch('/api/me');
            const data = await response.json();
            this.userId = data.user_id;
        } catch (error) {
            console.error('Failed to get user ID:', error);
            this.userId = 'guest_' + Math.random().toString(36).substr(2, 9);
        }
    }
    
    // ========================================
    // HOTSPOT INTERACTIONS
    // ========================================
    
    setupHotspots() {
        // Hotspot 1: Stage (Avatar Maker)
        document.getElementById('stage-hotspot').addEventListener('click', () => {
            this.enterStageView();
        });
        
        // Hotspot 2: Typewriter (Functional)
        document.getElementById('typewriter-hotspot').addEventListener('click', () => {
            this.enterTypewriterView();
        });
        
        // Hotspot 3: Vanity (Makeup/Hair)
        document.getElementById('vanity-hotspot').addEventListener('click', () => {
            this.enterVanityView();
        });
        
        // Exit door
        document.getElementById('exit-door').addEventListener('click', () => {
            if (confirm('Go to Green Room?')) {
                window.location.href = '/greenroom';
            }
        });
        
        // Back buttons for each view
        document.getElementById('back-to-room').addEventListener('click', () => {
            this.returnToRoom();
        });
        
        document.getElementById('back-from-stage').addEventListener('click', () => {
            this.returnToRoom();
        });
        
        document.getElementById('back-from-vanity').addEventListener('click', () => {
            this.returnToRoom();
        });
    }
    
    enterStageView() {
        this.roomView.classList.remove('active');
        this.stageView.classList.add('active');
        
        // Initialize Humphrey Avatar Maker with delay for script loading
        setTimeout(() => {
            this.initializeHumphreyAvatarMaker();
        }, 500); // Give scripts time to load
    }
    
    initializeHumphreyAvatarMaker() {
        // Check if already initialized
        if (this.humphreyAvatarMaker) {
            console.log('🕵️‍♂️ Detective Humphrey already active!');
            return;
        }
        
        const container = document.getElementById('humphrey-avatar-container');
        if (!container) {
            console.error('🚨 Humphrey container not found!');
            return;
        }
        
        // Check if HumphreyAvatarMaker class is available
        if (typeof window.HumphreyAvatarMaker === 'undefined') {
            console.error('🚨 HumphreyAvatarMaker class not loaded!');
            container.innerHTML = `
                <div style="text-align: center; color: #DEB887; padding: 40px;">
                    <div style="font-size: 48px;">🕵️‍♂️💔</div>
                    <h3>Detective Humphrey Missing!</h3>
                    <p>Avatar maker failed to load. Please refresh the page.</p>
                    <button onclick="location.reload()" style="padding: 10px 20px; background: #8B4513; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        Try Again
                    </button>
                </div>
            `;
            return;
        }
        
        // Check if Three.js is loaded
        if (typeof THREE === 'undefined') {
            console.error('🚨 Three.js not loaded!');
            container.innerHTML = `
                <div style="text-align: center; color: #DEB887; padding: 40px;">
                    <div style="font-size: 48px;">🔍💔</div>
                    <h3>3D Library Missing!</h3>
                    <p>Three.js failed to load. Check your internet connection.</p>
                    <button onclick="location.reload()" style="padding: 10px 20px; background: #8B4513; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        Retry
                    </button>
                </div>
            `;
            return;
        }
        
        try {
            // Remove loading state
            container.classList.remove('humphrey-loading');
            
            // Initialize the 3D avatar maker
            this.humphreyAvatarMaker = new window.HumphreyAvatarMaker(container);
            
            console.log('✅ Detective Humphrey Avatar Maker initialized successfully!');
        } catch (error) {
            console.error('🚨 Error initializing Humphrey:', error);
            container.innerHTML = `
                <div style="text-align: center; color: #DEB887; padding: 40px;">
                    <div style="font-size: 48px;">🕵️‍♂️⚠️</div>
                    <h3>Detective Humphrey Investigation Failed!</h3>
                    <p>Error: ${error.message}</p>
                    <button onclick="location.reload()" style="padding: 10px 20px; background: #8B4513; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        Restart Investigation
                    </button>
                </div>
            `;
        }
    }
    
    enterTypewriterView() {
        this.roomView.classList.remove('active');
        this.typewriterView.classList.add('active');
        this.paperContent.focus();
    }
    
    enterVanityView() {
        this.roomView.classList.remove('active');
        this.vanityView.classList.add('active');
    }
    
    returnToRoom() {
        // Check for unsaved changes in typewriter
        if (this.typewriterView.classList.contains('active') && this.hasUnsavedChanges()) {
            if (confirm('You have unsaved changes. Leave anyway?')) {
                this.autoSave();
            } else {
                return;
            }
        }
        
        // Return to room view
        this.typewriterView.classList.remove('active');
        this.stageView.classList.remove('active');
        this.vanityView.classList.remove('active');
        this.roomView.classList.add('active');
    }
    
    // ========================================
    // TYPEWRITER CONTROLS
    // ========================================
    
    setupTypewriterControls() {
        document.getElementById('menu-btn').addEventListener('click', () => {
            this.toggleMenu();
        });
    }
    
    // ========================================
    // KEYBOARD INPUT & TYPING
    // ========================================
    
    setupKeyboardInput() {
        if (!this.paperContent) return;
        
        this.paperContent.addEventListener('keydown', (e) => {
            this.handleKeyPress(e);
        });
        
        this.paperContent.addEventListener('input', () => {
            this.updateDocumentContent();
        });
    }
    
    handleKeyPress(e) {
        // Enter key
        if (e.key === 'Enter') {
            e.preventDefault();
            this.playSound('return');
            this.insertNewLine();
            this.currentLinePosition = 0;
            return;
        }
        
        // Printable characters
        if (e.key.length === 1) {
            this.playSound('keystroke');
            this.currentLinePosition++;
            
            // Line end ding
            if (this.currentLinePosition >= this.charactersPerLine) {
                this.playSound('ding');
                this.currentLinePosition = 0;
            }
        }
        
        // Backspace
        if (e.key === 'Backspace') {
            this.playSound('keystroke');
            this.currentLinePosition = Math.max(0, this.currentLinePosition - 1);
        }
    }
    
    insertNewLine() {
        const selection = window.getSelection();
        const range = selection.getRangeAt(0);
        range.deleteContents();
        
        const br = document.createElement('br');
        range.insertNode(br);
        
        range.setStartAfter(br);
        range.setEndAfter(br);
        selection.removeAllRanges();
        selection.addRange(range);
        
        this.updateDocumentContent();
    }
    
    updateDocumentContent() {
        this.currentDocument.content = this.paperContent.innerText;
        this.currentDocument.lastModified = new Date().toISOString();
    }
    
    // ========================================
    // SOUND EFFECTS
    // ========================================
    
    playSound(type) {
        let audio;
        
        switch(type) {
            case 'keystroke':
                audio = this.audioKeystroke;
                break;
            case 'ding':
                audio = this.audioDing;
                break;
            case 'return':
                audio = this.audioReturn;
                break;
            default:
                return;
        }
        
        if (audio) {
            const clone = audio.cloneNode();
            clone.volume = 0.4;
            clone.play().catch(() => {});
        }
    }
    
    // ========================================
    // MENU SYSTEM
    // ========================================
    
    setupMenuSystem() {
        const menuOptions = document.querySelectorAll('.menu-option');
        
        menuOptions.forEach(option => {
            option.addEventListener('click', () => {
                const action = option.dataset.action;
                this.handleMenuAction(action);
            });
        });
    }
    
    toggleMenu() {
        const menuOverlay = document.getElementById('menu-overlay');
        menuOverlay.classList.toggle('menu-hidden');
    }
    
    handleMenuAction(action) {
        this.toggleMenu();
        
        switch(action) {
            case 'new':
                this.newDocument();
                break;
            case 'load':
                this.openDocumentLibrary();
                break;
            case 'save':
                this.openSaveDialog();
                break;
            case 'message':
                this.composeMessage();
                break;
            case 'scripts':
                this.openScriptsLibrary();
                break;
            case 'close':
                break;
        }
    }
    
    // ========================================
    // DOCUMENT MANAGEMENT
    // ========================================
    
    newDocument() {
        if (this.hasUnsavedChanges()) {
            if (!confirm('You have unsaved changes. Create new document anyway?')) {
                return;
            }
        }
        
        this.currentDocument = {
            title: 'Untitled Document',
            content: '',
            category: 'general',
            lastModified: new Date().toISOString()
        };
        
        this.paperContent.innerText = '';
        this.docTitle.textContent = this.currentDocument.title;
        this.currentLinePosition = 0;
    }
    
    async saveDocument() {
        try {
            // Save to localStorage as fallback
            this.saveToLocalStorage();
            return true;
        } catch (error) {
            console.error('Save error:', error);
            return false;
        }
    }
    
    hasUnsavedChanges() {
        const savedContent = localStorage.getItem(`doc_autosave_${this.userId}`);
        return this.currentDocument.content !== (savedContent || '');
    }
    
    autoSave() {
        localStorage.setItem(`doc_autosave_${this.userId}`, this.currentDocument.content);
        localStorage.setItem(`doc_autosave_title_${this.userId}`, this.currentDocument.title);
    }
    
    loadAutoSave() {
        const savedContent = localStorage.getItem(`doc_autosave_${this.userId}`);
        const savedTitle = localStorage.getItem(`doc_autosave_title_${this.userId}`);
        
        if (savedContent && this.paperContent) {
            this.currentDocument.content = savedContent;
            this.currentDocument.title = savedTitle || 'Untitled Document';
            this.paperContent.innerText = savedContent;
            this.docTitle.textContent = this.currentDocument.title;
        }
    }
    
    saveToLocalStorage() {
        const key = `doc_${this.userId}_${Date.now()}`;
        localStorage.setItem(key, JSON.stringify(this.currentDocument));
        
        const index = JSON.parse(localStorage.getItem(`doc_index_${this.userId}`) || '[]');
        index.push({
            key: key,
            title: this.currentDocument.title,
            category: this.currentDocument.category,
            lastModified: this.currentDocument.lastModified
        });
        localStorage.setItem(`doc_index_${this.userId}`, JSON.stringify(index));
    }
    
    listFromLocalStorage(category = null) {
        const index = JSON.parse(localStorage.getItem(`doc_index_${this.userId}`) || '[]');
        
        if (category) {
            return index.filter(doc => doc.category === category);
        }
        
        return index;
    }
    
    loadDocument(key) {
        const docData = localStorage.getItem(key);
        if (docData) {
            this.currentDocument = JSON.parse(docData);
            this.paperContent.innerText = this.currentDocument.content;
            this.docTitle.textContent = this.currentDocument.title;
            this.currentLinePosition = 0;
        }
    }
    
    // ========================================
    // MODAL DIALOGS
    // ========================================
    
    setupModals() {
        document.getElementById('confirm-save').addEventListener('click', () => {
            this.confirmSave();
        });
        
        document.getElementById('cancel-save').addEventListener('click', () => {
            this.closeSaveDialog();
        });
        
        document.getElementById('close-modal').addEventListener('click', () => {
            this.closeLibraryModal();
        });
    }
    
    openSaveDialog() {
        const saveDialog = document.getElementById('save-dialog');
        const nameInput = document.getElementById('save-name');
        const categorySelect = document.getElementById('save-category');
        
        nameInput.value = this.currentDocument.title === 'Untitled Document' 
            ? '' 
            : this.currentDocument.title;
        categorySelect.value = this.currentDocument.category;
        
        saveDialog.classList.add('active');
        nameInput.focus();
    }
    
    closeSaveDialog() {
        const saveDialog = document.getElementById('save-dialog');
        saveDialog.classList.remove('active');
    }
    
    async confirmSave() {
        const nameInput = document.getElementById('save-name');
        const categorySelect = document.getElementById('save-category');
        
        const title = nameInput.value.trim() || 'Untitled Document';
        const category = categorySelect.value;
        
        this.currentDocument.title = title;
        this.currentDocument.category = category;
        this.docTitle.textContent = title;
        
        const success = await this.saveDocument();
        
        if (success) {
            this.closeSaveDialog();
            this.showNotification('Document saved successfully!');
        } else {
            alert('Failed to save document. Please try again.');
        }
    }
    
    async openDocumentLibrary() {
        const modal = document.getElementById('library-modal');
        const modalTitle = document.getElementById('modal-title');
        const documentList = document.getElementById('document-list');
        
        modalTitle.textContent = 'Document Library';
        documentList.innerHTML = '<p style="text-align:center; color:#666;">Loading documents...</p>';
        
        modal.classList.add('active');
        
        const documents = this.listFromLocalStorage();
        
        if (documents.length === 0) {
            documentList.innerHTML = '<p style="text-align:center; color:#666;">No saved documents found.</p>';
            return;
        }
        
        documentList.innerHTML = '';
        
        documents.forEach(doc => {
            const item = document.createElement('div');
            item.className = 'document-item';
            item.innerHTML = `
                <div>
                    <div class="document-item-title">${this.escapeHtml(doc.title)}</div>
                    <div class="document-item-meta">
                        ${doc.category} • ${this.formatDate(doc.lastModified)}
                    </div>
                </div>
            `;
            
            item.addEventListener('click', () => {
                this.loadDocument(doc.key);
                this.closeLibraryModal();
            });
            
            documentList.appendChild(item);
        });
    }
    
    closeLibraryModal() {
        const modal = document.getElementById('library-modal');
        modal.classList.remove('active');
    }
    
    async openScriptsLibrary() {
        const modal = document.getElementById('library-modal');
        const modalTitle = document.getElementById('modal-title');
        const documentList = document.getElementById('document-list');
        
        modalTitle.textContent = 'Scripts Library';
        documentList.innerHTML = '<p style="text-align:center; color:#666;">Loading scripts...</p>';
        
        modal.classList.add('active');
        
        const scripts = this.listFromLocalStorage('script');
        
        if (scripts.length === 0) {
            documentList.innerHTML = '<p style="text-align:center; color:#666;">No scripts found. Create one by saving a document as "Script" category.</p>';
            return;
        }
        
        documentList.innerHTML = '';
        
        scripts.forEach(doc => {
            const item = document.createElement('div');
            item.className = 'document-item';
            item.innerHTML = `
                <div>
                    <div class="document-item-title">📜 ${this.escapeHtml(doc.title)}</div>
                    <div class="document-item-meta">
                        ${this.formatDate(doc.lastModified)}
                    </div>
                </div>
            `;
            
            item.addEventListener('click', () => {
                this.loadDocument(doc.key);
                this.closeLibraryModal();
            });
            
            documentList.appendChild(item);
        });
    }
    
    composeMessage() {
        this.currentDocument = {
            title: 'New Message',
            content: '',
            category: 'message',
            lastModified: new Date().toISOString()
        };
        
        this.paperContent.innerText = '';
        this.docTitle.textContent = 'New Message';
        this.currentLinePosition = 0;
        
        const template = `To: [Recipient]\nFrom: ${this.userId}\nDate: ${new Date().toLocaleString()}\n\n---\n\n`;
        this.paperContent.innerText = template;
        this.updateDocumentContent();
        
        this.moveCursorToEnd();
    }
    
    moveCursorToEnd() {
        const range = document.createRange();
        const selection = window.getSelection();
        
        range.selectNodeContents(this.paperContent);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
        
        this.paperContent.focus();
    }
    
    // ========================================
    // UTILITIES
    // ========================================
    
    showNotification(message) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(to right, #2d1f15, #4a2f1f);
            color: #daa520;
            padding: 15px 25px;
            border-radius: 8px;
            border: 2px solid #daa520;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.6);
            z-index: 10000;
            font-family: Georgia, serif;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.5s';
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatDate(isoString) {
        const date = new Date(isoString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
}

// ========================================
// INITIALIZE SYSTEM
// ========================================

let dressingRoom;

document.addEventListener('DOMContentLoaded', () => {
    dressingRoom = new DressingRoomSystem();
});

// Auto-save every 30 seconds
setInterval(() => {
    if (dressingRoom && dressingRoom.typewriterView.classList.contains('active')) {
        dressingRoom.autoSave();
    }
}, 30000);

// Save on page unload
window.addEventListener('beforeunload', (e) => {
    if (dressingRoom && dressingRoom.hasUnsavedChanges()) {
        dressingRoom.autoSave();
    }
});
