// RSS Triage System - Frontend JavaScript (3-Panel Version)

// State
let authToken = null;
let currentUser = null;
let isProcessing = false;
let lastAction = null; // Track last action for undo: {itemId, action}
let panelData = {
    priority1: { item: null, remaining: 0 },
    standard: { item: null, remaining: 0 },
    social: { item: null, remaining: 0 }
};

// Check for auth token in localStorage
authToken = localStorage.getItem('kairos_token');
const storedUser = localStorage.getItem('kairos_user');
if (storedUser) {
    try {
        currentUser = JSON.parse(storedUser);
    } catch (e) {
        currentUser = null;
    }
}

// Elements
const helpModal = document.getElementById('help-modal');
const feedModal = document.getElementById('feed-modal');
const statusMessage = document.getElementById('status-message');
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
        // Auth required - redirect to login
        localStorage.removeItem('kairos_token');
        localStorage.removeItem('kairos_user');
        window.location.href = '/login.html';
        throw new Error('Authentication required');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

// Logout function
async function logout() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: getAuthHeaders()
        });
    } catch (e) {
        // Ignore errors during logout
    }
    localStorage.removeItem('kairos_token');
    localStorage.removeItem('kairos_user');
    window.location.href = '/login.html';
}

// Get current user info
function getCurrentUser() {
    return currentUser;
}

// Panel item rendering
function renderItem(panel, item) {
    if (!item) {
        return `
            <div class="empty-panel">
                <p>No pending items</p>
            </div>
        `;
    }

    const date = new Date(item.published_date);
    const dateStr = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });

    return `
        <article class="feed-item" data-panel="${panel}" data-item-id="${item.id}">
            <div class="item-header">
                <h3 class="item-title">${escapeHtml(item.title)}</h3>
                <div class="item-meta">
                    <span class="source">${escapeHtml(item.feed_name)}</span>
                    <span class="separator">•</span>
                    <span class="date">${dateStr}</span>
                </div>
            </div>

            <div class="item-body">
                <p class="item-summary">${escapeHtml(item.summary || 'No summary available.')}</p>
                <a href="${item.url}" target="_blank" class="read-more">Read full article →</a>
            </div>

            <div class="item-actions">
                <button class="btn btn-alert" onclick="triageItem('${panel}', ${item.id}, 'alert')">
                    <span class="btn-icon">🚨</span>
                    <span class="btn-text">Alert</span>
                </button>

                <button class="btn btn-digest" onclick="triageItem('${panel}', ${item.id}, 'digest')">
                    <span class="btn-icon">📋</span>
                    <span class="btn-text">Digest</span>
                </button>

                <button class="btn btn-skip" onclick="triageItem('${panel}', ${item.id}, 'skip')">
                    <span class="btn-icon">⏭️</span>
                    <span class="btn-text">Skip</span>
                </button>
            </div>
        </article>
    `;
}

// Load items for a specific panel
async function loadPanelItem(panel) {
    const contentEl = document.getElementById(`content-${panel}`);
    const countEl = document.getElementById(`count-${panel}`);

    contentEl.innerHTML = '<div class="loading-panel"><div class="spinner-small"></div> Loading...</div>';

    try {
        const data = await apiCall(`/api/items/next/${panel}`);

        panelData[panel].item = data.item;
        panelData[panel].remaining = data.remaining;

        contentEl.innerHTML = renderItem(panel, data.item);
        countEl.textContent = `${data.remaining} item${data.remaining !== 1 ? 's' : ''}`;

    } catch (error) {
        console.error(`Error loading ${panel} panel:`, error);
        contentEl.innerHTML = `<div class="error-panel">Error: ${error.message}</div>`;
        countEl.textContent = 'Error';
    }
}

// Load all panels
async function loadAllPanels() {
    await Promise.all([
        loadPanelItem('priority1'),
        loadPanelItem('standard'),
        loadPanelItem('social')
    ]);
}

// Triage item
async function triageItem(panel, itemId, action) {
    if (isProcessing) return;

    isProcessing = true;
    const article = document.querySelector(`[data-panel="${panel}"][data-item-id="${itemId}"]`);
    if (article) {
        article.style.opacity = '0.5';
        article.querySelectorAll('button').forEach(btn => btn.disabled = true);
    }

    try {
        const result = await apiCall(`/api/items/${itemId}/triage`, {
            method: 'POST',
            body: JSON.stringify({ action })
        });

        // Save last action for undo
        lastAction = { itemId, action, panel };
        undoBtn.classList.remove('hidden');

        // Show status message
        statusMessage.textContent = result.message;
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 3000);

        // Reload the panel
        setTimeout(() => {
            loadPanelItem(panel);
            isProcessing = false;
        }, 300);

    } catch (error) {
        console.error('Error triaging item:', error);
        alert(`Error: ${error.message}`);
        if (article) {
            article.style.opacity = '1';
            article.querySelectorAll('button').forEach(btn => btn.disabled = false);
        }
        isProcessing = false;
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

        const panel = lastAction.panel;
        lastAction = null;
        undoBtn.classList.add('hidden');

        statusMessage.textContent = 'Action undone';
        setTimeout(() => {
            statusMessage.textContent = '';
        }, 2000);

        // Reload the affected panel
        await loadPanelItem(panel);
        isProcessing = false;
        undoBtn.disabled = false;

    } catch (error) {
        console.error('Error undoing action:', error);
        alert(`Error: ${error.message}`);
        isProcessing = false;
        undoBtn.disabled = false;
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

        lastAction = null;
        undoBtn.classList.add('hidden');

        setTimeout(() => {
            loadAllPanels();
            isProcessing = false;
            skipAllBtn.disabled = false;
        }, 1000);

    } catch (error) {
        console.error('Error skipping all items:', error);
        alert(`Error: ${error.message}`);
        isProcessing = false;
        skipAllBtn.disabled = false;
    }
}

// Feed Management
async function showFeedManager() {
    feedModal.classList.remove('hidden');
    await loadFeeds();
}

function hideFeedManager() {
    feedModal.classList.add('hidden');
}

feedModal.addEventListener('click', (e) => {
    if (e.target === feedModal) {
        hideFeedManager();
    }
});

async function loadFeeds() {
    const feedListLoading = document.getElementById('feed-list-loading');
    const feedList = document.getElementById('feed-list');

    feedListLoading.classList.remove('hidden');
    feedList.innerHTML = '';

    try {
        const data = await apiCall('/api/feeds');
        feedListLoading.classList.add('hidden');

        if (!data.feeds || data.feeds.length === 0) {
            feedList.innerHTML = '<div class="feed-list-empty">No feeds configured yet. Add your first feed above!</div>';
            return;
        }

        // Group by category
        const rssFeeds = data.feeds.filter(f => f.category === 'RSS').sort((a, b) => a.priority - b.priority);
        const socialFeeds = data.feeds.filter(f => f.category === 'Social').sort((a, b) => a.priority - b.priority);

        let html = '';

        if (rssFeeds.length > 0) {
            html += '<div class="feed-category-header">RSS Feeds</div>';
            html += rssFeeds.map(feed => renderFeedRow(feed)).join('');
        }

        if (socialFeeds.length > 0) {
            html += '<div class="feed-category-header">Social Media</div>';
            html += socialFeeds.map(feed => renderFeedRow(feed)).join('');
        }

        feedList.innerHTML = html;

    } catch (error) {
        console.error('Error loading feeds:', error);
        feedListLoading.classList.add('hidden');
        feedList.innerHTML = `<div class="feed-list-empty" style="color: var(--neon-pink);">Error loading feeds: ${error.message}</div>`;
    }
}

function renderFeedRow(feed) {
    return `
        <div class="feed-item-row" id="feed-row-${feed.id}">
            <div class="feed-info">
                <div class="feed-info-name">${escapeHtml(feed.name || 'Unnamed Feed')}</div>
                <div class="feed-info-url">${escapeHtml(feed.url)}</div>
                <div class="feed-info-meta">
                    <span class="feed-priority">Priority: ${feed.priority}</span>
                    <span class="feed-category">${feed.category}</span>
                    <span class="feed-status ${feed.active ? 'active' : 'inactive'}">
                        ${feed.active ? '✓ Active' : '✗ Inactive'}
                    </span>
                </div>
            </div>
            <div class="feed-actions">
                <button class="btn-edit" onclick="editFeed(${feed.id})">
                    Edit
                </button>
                <button class="btn-delete" onclick="deleteFeed(${feed.id}, '${escapeHtml(feed.name || feed.url)}')">
                    Delete
                </button>
            </div>
        </div>
    `;
}

function renderFeedEditRow(feed) {
    return `
        <div class="feed-item-row feed-edit-row" id="feed-row-${feed.id}">
            <div class="feed-edit-form">
                <div class="form-group">
                    <label>Name</label>
                    <input type="text" id="edit-name-${feed.id}" value="${escapeHtml(feed.name || '')}" placeholder="Feed name">
                </div>
                <div class="form-group">
                    <label>Priority (1-5)</label>
                    <input type="number" id="edit-priority-${feed.id}" min="1" max="5" value="${feed.priority}">
                </div>
                <div class="form-group">
                    <label>Category</label>
                    <select id="edit-category-${feed.id}">
                        <option value="RSS" ${feed.category === 'RSS' ? 'selected' : ''}>RSS</option>
                        <option value="Social" ${feed.category === 'Social' ? 'selected' : ''}>Social</option>
                    </select>
                </div>
                <div class="feed-edit-actions">
                    <button class="btn-save" onclick="saveFeed(${feed.id})">Save</button>
                    <button class="btn-cancel" onclick="cancelEditFeed(${feed.id})">Cancel</button>
                </div>
            </div>
        </div>
    `;
}

async function addFeed(event) {
    event.preventDefault();

    const urlInput = document.getElementById('feed-url');
    const nameInput = document.getElementById('feed-name');
    const priorityInput = document.getElementById('feed-priority');
    const submitBtn = event.target.querySelector('button[type="submit"]');

    const feedData = {
        url: urlInput.value.trim(),
        name: nameInput.value.trim() || null,
        priority: parseInt(priorityInput.value),
        category: 'RSS'
    };

    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';

    try {
        await apiCall('/api/feeds', {
            method: 'POST',
            body: JSON.stringify(feedData)
        });

        urlInput.value = '';
        nameInput.value = '';
        priorityInput.value = '3';

        await loadFeeds();
        showFeedSuccess('RSS feed added successfully!');

    } catch (error) {
        console.error('Error adding feed:', error);
        alert(`Error adding feed: ${error.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add RSS Feed';
    }
}

async function addMastodonUser(event) {
    event.preventDefault();

    const handleInput = document.getElementById('mastodon-handle');
    const priorityInput = document.getElementById('mastodon-priority');
    const submitBtn = event.target.querySelector('button[type="submit"]');

    const handle = handleInput.value.trim();

    // Parse Mastodon handle: @username@instance.social
    const match = handle.match(/@?([^@]+)@([^@]+)/);
    if (!match) {
        alert('Invalid Mastodon handle format. Use: @username@instance.social');
        return;
    }

    const username = match[1];
    const instance = match[2];
    const rssUrl = `https://${instance}/@${username}.rss`;
    const displayName = `@${username}@${instance}`;

    const feedData = {
        url: rssUrl,
        name: displayName,
        priority: parseInt(priorityInput.value),
        category: 'Social'
    };

    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';

    try {
        await apiCall('/api/feeds', {
            method: 'POST',
            body: JSON.stringify(feedData)
        });

        handleInput.value = '';
        priorityInput.value = '3';

        await loadFeeds();
        showFeedSuccess(`Mastodon user ${displayName} added successfully!`);

    } catch (error) {
        console.error('Error adding Mastodon user:', error);
        alert(`Error adding Mastodon user: ${error.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add Mastodon User';
    }
}

function showFeedSuccess(message) {
    const feedListContainer = document.querySelector('.feed-list-container');
    const successMsg = document.createElement('div');
    successMsg.style.cssText = 'padding: 12px; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; border-radius: 6px; margin-bottom: 12px; color: #10b981; font-size: 14px;';
    successMsg.textContent = '✓ ' + message;
    feedListContainer.insertBefore(successMsg, feedListContainer.firstChild);
    setTimeout(() => successMsg.remove(), 5000);
}

let feedBeingEdited = null;

async function editFeed(feedId) {
    // Get current feed data
    try {
        const data = await apiCall('/api/feeds');
        const feed = data.feeds.find(f => f.id === feedId);

        if (!feed) {
            alert('Feed not found');
            return;
        }

        // Store original feed data for cancel
        feedBeingEdited = { ...feed };

        // Replace the row with edit form
        const rowElement = document.getElementById(`feed-row-${feedId}`);
        if (rowElement) {
            rowElement.outerHTML = renderFeedEditRow(feed);
        }

    } catch (error) {
        console.error('Error loading feed for edit:', error);
        alert(`Error: ${error.message}`);
    }
}

async function saveFeed(feedId) {
    const nameInput = document.getElementById(`edit-name-${feedId}`);
    const priorityInput = document.getElementById(`edit-priority-${feedId}`);
    const categorySelect = document.getElementById(`edit-category-${feedId}`);

    const feedData = {
        url: feedBeingEdited.url, // URL can't be changed
        name: nameInput.value.trim() || null,
        priority: parseInt(priorityInput.value),
        category: categorySelect.value
    };

    try {
        await apiCall(`/api/feeds/${feedId}`, {
            method: 'PUT',
            body: JSON.stringify(feedData)
        });

        feedBeingEdited = null;
        await loadFeeds();
        showFeedSuccess('Feed updated successfully!');

    } catch (error) {
        console.error('Error updating feed:', error);
        alert(`Error updating feed: ${error.message}`);
    }
}

function cancelEditFeed(feedId) {
    if (!feedBeingEdited) return;

    // Restore original row
    const rowElement = document.getElementById(`feed-row-${feedId}`);
    if (rowElement) {
        rowElement.outerHTML = renderFeedRow(feedBeingEdited);
    }

    feedBeingEdited = null;
}

async function deleteFeed(feedId, feedName) {
    if (!confirm(`Delete feed "${feedName}"?\n\nThis will also remove all items from this feed.`)) {
        return;
    }

    try {
        await apiCall(`/api/feeds/${feedId}`, {
            method: 'DELETE'
        });

        await loadFeeds();

    } catch (error) {
        console.error('Error deleting feed:', error);
        alert(`Error deleting feed: ${error.message}`);
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Help modal
function showHelp() {
    helpModal.classList.remove('hidden');
}

function hideHelp() {
    helpModal.classList.add('hidden');
}

helpModal.addEventListener('click', (e) => {
    if (e.target === helpModal) {
        hideHelp();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (!helpModal.classList.contains('hidden') || !feedModal.classList.contains('hidden') || isProcessing) return;

    const key = e.key.toLowerCase();

    if (key === '?') {
        e.preventDefault();
        showHelp();
        return;
    }

    if (key === 'u' && lastAction) {
        e.preventDefault();
        undoLastAction();
        return;
    }

    // Find the focused panel or use the first available item
    let targetPanel = null;
    let targetItem = null;

    for (const panel of ['priority1', 'standard', 'social']) {
        const item = panelData[panel].item;
        if (item) {
            targetPanel = panel;
            targetItem = item;
            break;
        }
    }

    if (!targetItem) return;

    if (key === 'a') {
        e.preventDefault();
        triageItem(targetPanel, targetItem.id, 'alert');
    } else if (key === 'd') {
        e.preventDefault();
        triageItem(targetPanel, targetItem.id, 'digest');
    } else if (key === 's') {
        e.preventDefault();
        triageItem(targetPanel, targetItem.id, 'skip');
    }
});

// Initialize user display in header
function initUserDisplay() {
    const header = document.querySelector('header');
    const statsDiv = header.querySelector('.stats');

    // Create user info element
    const userInfo = document.createElement('div');
    userInfo.className = 'user-info';

    if (currentUser) {
        userInfo.innerHTML = `
            <span class="user-name">${escapeHtml(currentUser.username)}</span>
            ${currentUser.role === 'admin' ? '<span class="admin-badge">Admin</span>' : ''}
            <button class="btn-logout" onclick="logout()" title="Sign out">Logout</button>
        `;
        // Add admin link if admin
        if (currentUser.role === 'admin') {
            const adminLink = document.createElement('a');
            adminLink.href = '/admin.html';
            adminLink.className = 'btn-admin';
            adminLink.textContent = 'Admin';
            userInfo.insertBefore(adminLink, userInfo.querySelector('.btn-logout'));
        }
    }

    // Insert user info before stats
    statsDiv.insertBefore(userInfo, statsDiv.firstChild);
}

// Check authentication and redirect if needed
async function checkAuth() {
    if (!authToken) {
        window.location.href = '/login.html';
        return false;
    }

    try {
        const userData = await apiCall('/api/auth/me');
        currentUser = userData;
        localStorage.setItem('kairos_user', JSON.stringify(userData));
        return true;
    } catch (error) {
        // apiCall will redirect to login on 401
        return false;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Check auth first
    if (!authToken) {
        window.location.href = '/login.html';
        return;
    }

    // Verify token is valid
    try {
        const userData = await apiCall('/api/auth/me');
        currentUser = userData;
        localStorage.setItem('kairos_user', JSON.stringify(userData));
    } catch (error) {
        // Will be redirected to login
        return;
    }

    // Set up user display
    initUserDisplay();

    // Load panels
    loadAllPanels();

    // Refresh panels periodically
    setInterval(async () => {
        if (!isProcessing) {
            try {
                // Update counts without full reload
                for (const panel of ['priority1', 'standard', 'social']) {
                    const data = await apiCall(`/api/items/next/${panel}`);
                    const countEl = document.getElementById(`count-${panel}`);
                    if (countEl) {
                        countEl.textContent = `${data.remaining} item${data.remaining !== 1 ? 's' : ''}`;
                    }
                }
            } catch (error) {
                console.error('Error refreshing stats:', error);
            }
        }
    }, 30000); // Every 30 seconds
});
