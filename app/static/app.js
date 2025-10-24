// RSS Triage System - Frontend JavaScript

// State
let currentItem = null;
let authToken = null;
let isProcessing = false;
let lastAction = null; // Track last action for undo: {itemId, action}

// Check for auth token in localStorage
authToken = localStorage.getItem('rss_triage_token');

// Elements
const loadingScreen = document.getElementById('loading-screen');
const noItemsScreen = document.getElementById('no-items-screen');
const itemScreen = document.getElementById('item-screen');
const errorScreen = document.getElementById('error-screen');
const remainingCount = document.getElementById('remaining-count');
const statusMessage = document.getElementById('status-message');
const helpModal = document.getElementById('help-modal');
const undoBtn = document.getElementById('undo-btn');

// API helpers
function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    return headers;
}

async function apiCall(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        ...options,
        headers: {
            ...getAuthHeaders(),
            ...(options.headers || {})
        }
    });

    if (response.status === 401) {
        // Auth required
        const token = prompt('Enter authentication token:');
        if (token) {
            authToken = token;
            localStorage.setItem('rss_triage_token', token);
            // Retry request
            return apiCall(endpoint, options);
        } else {
            throw new Error('Authentication required');
        }
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

// Screen management
function showScreen(screen) {
    [loadingScreen, noItemsScreen, itemScreen, errorScreen].forEach(s => {
        s.classList.add('hidden');
    });
    screen.classList.remove('hidden');
}

function showError(message) {
    document.getElementById('error-message').textContent = message;
    showScreen(errorScreen);
}

// Load next item
async function loadNextItem() {
    if (isProcessing) return;

    showScreen(loadingScreen);
    statusMessage.textContent = '';

    try {
        const data = await apiCall('/api/items/next');

        if (!data.item) {
            // No items
            remainingCount.textContent = '0 items pending';
            showScreen(noItemsScreen);
            return;
        }

        currentItem = data.item;
        remainingCount.textContent = `${data.remaining} item${data.remaining !== 1 ? 's' : ''} pending`;

        // Populate item details
        document.getElementById('item-title').textContent = currentItem.title;
        document.getElementById('item-source').textContent = currentItem.feed_name;

        // Format date
        const date = new Date(currentItem.published_date);
        const dateStr = date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('item-date').textContent = dateStr;

        document.getElementById('item-summary').textContent = currentItem.summary || 'No summary available.';

        const link = document.getElementById('item-link');
        link.href = currentItem.url;

        showScreen(itemScreen);

    } catch (error) {
        console.error('Error loading item:', error);
        showError(error.message);
    }
}

// Triage item
async function triageItem(action) {
    if (isProcessing || !currentItem) return;

    isProcessing = true;
    const buttons = document.querySelectorAll('.item-actions .btn');
    buttons.forEach(btn => btn.disabled = true);

    try {
        const result = await apiCall(`/api/items/${currentItem.id}/triage`, {
            method: 'POST',
            body: JSON.stringify({ action })
        });

        // Save last action for undo
        lastAction = {
            itemId: currentItem.id,
            action: action
        };

        // Show undo button
        undoBtn.classList.remove('hidden');

        // Show status message
        statusMessage.textContent = result.message;
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 3000);

        // Load next item after short delay
        setTimeout(() => {
            isProcessing = false;
            buttons.forEach(btn => btn.disabled = false);
            loadNextItem();
        }, 500);

    } catch (error) {
        console.error('Error triaging item:', error);
        isProcessing = false;
        buttons.forEach(btn => btn.disabled = false);
        alert(`Error: ${error.message}`);
    }
}

// Undo last action
async function undoLastAction() {
    if (!lastAction || isProcessing) return;

    isProcessing = true;
    undoBtn.disabled = true;

    try {
        await apiCall(`/api/items/${lastAction.itemId}/undo`, {
            method: 'POST'
        });

        // Clear last action
        lastAction = null;
        undoBtn.classList.add('hidden');

        statusMessage.textContent = 'Action undone';
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 2000);

        // Reload current view
        isProcessing = false;
        undoBtn.disabled = false;
        loadNextItem();

    } catch (error) {
        console.error('Error undoing action:', error);
        isProcessing = false;
        undoBtn.disabled = false;
        alert(`Error: ${error.message}`);
    }
}

// Generate digest manually
async function generateDigestNow() {
    if (isProcessing) return;

    const confirmMsg = 'Generate digest now? This will create a digest file with all currently queued items.';
    if (!confirm(confirmMsg)) return;

    isProcessing = true;
    statusMessage.textContent = 'Generating digest...';

    try {
        const result = await apiCall('/api/digest/generate', {
            method: 'POST'
        });

        statusMessage.textContent = `Digest generated: ${result.items_count} items`;
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 5000);

        // Offer to download
        if (result.items_count > 0) {
            setTimeout(() => {
                if (confirm('Download digest file now?')) {
                    window.open('/api/digest/latest', '_blank');
                }
            }, 1000);
        }

    } catch (error) {
        console.error('Error generating digest:', error);
        alert(`Error: ${error.message}`);
    } finally {
        isProcessing = false;
    }
}

// Skip all pending items
async function skipAllItems() {
    if (isProcessing) return;

    const confirmMsg = 'Skip all pending items? This will mark all remaining items as skipped.';
    if (!confirm(confirmMsg)) return;

    isProcessing = true;
    const skipAllBtn = document.getElementById('skip-all-btn');
    skipAllBtn.disabled = true;
    statusMessage.textContent = 'Skipping all items...';

    try {
        const result = await apiCall('/api/items/skip-all', {
            method: 'POST'
        });

        statusMessage.textContent = result.message;
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 3000);

        // Clear last action since we're bulk skipping
        lastAction = null;
        undoBtn.classList.add('hidden');

        // Reload to show empty state
        setTimeout(() => {
            isProcessing = false;
            skipAllBtn.disabled = false;
            loadNextItem();
        }, 1000);

    } catch (error) {
        console.error('Error skipping all items:', error);
        isProcessing = false;
        skipAllBtn.disabled = false;
        alert(`Error: ${error.message}`);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Don't handle if modal is open or processing
    if (!helpModal.classList.contains('hidden') || isProcessing) return;

    const key = e.key.toLowerCase();

    // Help can be triggered anytime
    if (key === '?') {
        e.preventDefault();
        showHelp();
        return;
    }

    // Undo can be triggered if we have a last action
    if (key === 'u' && lastAction) {
        e.preventDefault();
        undoLastAction();
        return;
    }

    // Other shortcuts need a current item
    if (!currentItem) return;

    if (key === 'a') {
        e.preventDefault();
        triageItem('alert');
    } else if (key === 'd') {
        e.preventDefault();
        triageItem('digest');
    } else if (key === 's') {
        e.preventDefault();
        triageItem('skip');
    }
});

// Help modal
function showHelp() {
    helpModal.classList.remove('hidden');
}

function hideHelp() {
    helpModal.classList.add('hidden');
}

// Close modal on background click
helpModal.addEventListener('click', (e) => {
    if (e.target === helpModal) {
        hideHelp();
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadNextItem();

    // Refresh stats periodically
    setInterval(async () => {
        if (!isProcessing && currentItem) {
            try {
                const data = await apiCall('/api/items/next');
                if (data.remaining !== undefined) {
                    remainingCount.textContent = `${data.remaining} item${data.remaining !== 1 ? 's' : ''} pending`;
                }
            } catch (error) {
                console.error('Error refreshing stats:', error);
            }
        }
    }, 30000); // Every 30 seconds
});
