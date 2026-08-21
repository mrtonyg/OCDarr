document.addEventListener('DOMContentLoaded', function() {
    // Initialize - load content
    loadPopularShows();
    loadPopularMovies();

    // Add event listeners for episode selection in requests section
    const selectAllButtons = document.querySelectorAll('.select-all');
    const selectNoneButtons = document.querySelectorAll('.select-none');
    const cancelRequestButtons = document.querySelectorAll('.cancel-request');
    const directRequestForm = document.getElementById('direct-request-form');
    
    if (directRequestForm) {
        directRequestForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent default form submission
            
            const formData = new FormData(directRequestForm);
            
            fetch(directRequestForm.action, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                // Redirect to settings tab with requests section
                window.location.href = '/?section=settings&subsection=requests_section';
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while processing your request');
            });
        });
    }
    // Set up URL parameters and tab selection
    const urlParams = new URLSearchParams(window.location.search);
    const sectionParam = urlParams.get('section');
    const subsectionParam = urlParams.get('subsection');

    let tabToShow = 'shows-tab'; // Default
    
    if (sectionParam) {
        // If URL parameter exists, use it and save to localStorage
        tabToShow = sectionParam + '-tab';
        localStorage.setItem('lastActiveTab', tabToShow);
    } else if (localStorage.getItem('lastActiveTab')) {
        // If localStorage has a saved tab, use it
        tabToShow = localStorage.getItem('lastActiveTab');
    }

    // START: Insertion point for older script's logic
    var section = urlParams.get('section');
    var message = urlParams.get('message');
    var rule = urlParams.get('rule');
    
    if (section) {
        showSection(section, rule);
    }
    if (message && section === 'settings') {
        var messageDiv = document.createElement('div');
        messageDiv.className = 'alert alert-success';
        messageDiv.textContent = message;
        document.getElementById(section).prepend(messageDiv);
    }

    // Get rule select element
    var ruleSelect = document.getElementById('rule_name');
    
    // Add event listener for rule changes
    if (ruleSelect) {
        ruleSelect.addEventListener('change', loadRule);
    }
    // Initial rule load
    loadRule();

    selectAllButtons.forEach(button => {
        button.addEventListener('click', function() {
            const form = this.closest('form');
            form.querySelectorAll('.episode-checkbox').forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    });
    
    selectNoneButtons.forEach(button => {
        button.addEventListener('click', function() {
            const form = this.closest('form');
            form.querySelectorAll('.episode-checkbox').forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    });
    
    cancelRequestButtons.forEach(button => {
        button.addEventListener('click', function() {
            if (confirm('Are you sure you want to cancel this request?')) {
                const form = this.closest('form');
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'action';
                input.value = 'cancel';
                form.appendChild(input);
                form.submit();
            }
        });
    });
    // Jellyseerr Open Button
    const openJellyseerrBtn = document.getElementById('open-jellyseerr');
    if (openJellyseerrBtn) {
        openJellyseerrBtn.addEventListener('click', function() {
            // Retrieve Jellyseerr URL from hidden input
            const jellyseerrUrlInput = document.getElementById('jellyseerr-url');
            const jellyseerrUrl = jellyseerrUrlInput ? jellyseerrUrlInput.value : '';
            
            if (!jellyseerrUrl) {
                alert('Jellyseerr URL is not configured.');
                return;
            }
            
            // Get selected media type
            const mediaTypeRadios = document.getElementsByName('media_type');
            let selectedType = 'tv'; // default
            
            for (let radio of mediaTypeRadios) {
                if (radio.checked) {
                    selectedType = radio.value;
                    break;
                }
            }
            
            // Open appropriate discover page
            const discoverPath = selectedType === 'movie' ? '/discover/movies' : '/discover/tv';
            window.open(`${jellyseerrUrl}${discoverPath}`, '_blank');
        });
    }

    // NEW CODE: Check for pending requests every 30 seconds
    setInterval(checkForNewRequests, 30000);
    
    // Show the determined tab
    showMainTab(tabToShow);
    
    // If we're on the settings tab, restore the last active subsection
    if (tabToShow === 'settings-tab') {
        // Initialize rule form if it exists
        if (document.getElementById('rule_name') && document.getElementById('config-data')) {
            try {
                loadRule();
            } catch (e) {
                console.error("Error loading rule:", e);
            }
        }
    }
   
    // After adding content, check if we need to adjust the rows
    adjustScrollableRows();
});
// Add this to your index.js file
function scrollRowToStart(button) {
    const row = button.closest('.row-header').nextElementSibling;
    row.scrollTo({
        left: 0,
        behavior: 'smooth'
    });
}
// Add this function to toggle between the main settings and assign rules views
function toggleSettingsView(viewId) {
    // Hide all settings views
    document.querySelectorAll('.settings-view').forEach(view => {
        view.style.display = 'none';
    });
    
    // Show the selected view
    document.getElementById(viewId).style.display = 'block';
    
    // Update button states
    const mainButton = document.querySelector('button[onclick="toggleSettingsView(\'main-settings\')"]');
    const assignButton = document.querySelector('button[onclick="toggleSettingsView(\'assign-rules\')"]');
    
    if (viewId === 'main-settings') {
        mainButton.classList.add('btn-primary');
        mainButton.classList.remove('btn-secondary');
        assignButton.classList.add('btn-secondary');
        assignButton.classList.remove('btn-primary');
    } else {
        assignButton.classList.add('btn-primary');
        assignButton.classList.remove('btn-secondary');
        mainButton.classList.add('btn-secondary');
        mainButton.classList.remove('btn-primary');
    }
    
    // Save the current view to localStorage
    localStorage.setItem('lastSettingsView', viewId);
}

// Update the showMainTab function to restore the last settings view
function showMainTab(tabId) {
    // Hide all tabs
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabId);
    if (selectedTab) {
        selectedTab.style.display = 'block';
    } else {
        console.error("Tab not found:", tabId);
        // Fallback to shows tab
        const showsTab = document.getElementById('shows-tab');
        if (showsTab) showsTab.style.display = 'block';
    }
    
    // Save the current tab to localStorage
    localStorage.setItem('lastActiveTab', tabId);
    
    // If we're showing the settings tab, restore the last view and load rule data
    if (tabId === 'settings-tab') {
        const lastView = localStorage.getItem('lastSettingsView') || 'main-settings';
        toggleSettingsView(lastView);

        const ruleNameSelect = document.getElementById('rule_name');
        if (ruleNameSelect) {
            loadRule();
        }
    }

    // Dispatch custom event for sidebar to update active state
    window.dispatchEvent(new CustomEvent('tabChanged', {
        detail: { tabId: tabId }
    }));

    // On mobile, auto-close the sidebar after selection
    const sidebar = document.getElementById('sidebar');
    if (window.innerWidth <= 768 && sidebar && sidebar.classList.contains('expanded')) {
        sidebar.classList.remove('expanded');
    }
}

// Then update your HTML to include a new button in each row-controls div:
// <button class="scroll-btn scroll-start" onclick="scrollRowToStart(this)">⏮️</button>
// NEW FUNCTION: Check for pending requests
function checkForNewRequests() {
    // Fetch the current number of pending requests
    fetch('/api/pending-requests/count')
        .then(response => response.json())
        .then(data => {
            // If there are new requests and we're not already on the settings tab
            if (data.count > 0 && !document.getElementById('settings-tab').classList.contains('active')) {
                // Add a pulsing effect to the settings icon if it doesn't already have it
                const settingsIcon = document.querySelector('.menu-item:nth-child(2)');
                if (!settingsIcon.classList.contains('has-notifications')) {
                    settingsIcon.classList.add('has-notifications');
                   
                    // Add notification badge if it doesn't exist
                    if (!settingsIcon.querySelector('.notification-badge')) {
                        const badge = document.createElement('span');
                        badge.className = 'notification-badge';
                        badge.textContent = data.count;
                        settingsIcon.appendChild(badge);
                    } else {
                        // Update the count
                        settingsIcon.querySelector('.notification-badge').textContent = data.count;
                    }
                }
            }
        })
        .catch(error => console.error('Error checking for requests:', error));
}


function loadRule() {
    const ruleSelect = document.getElementById('rule_name');
    if (!ruleSelect) {
        return;
    }

    const configElement = document.getElementById('config-data');
    if (!configElement) {
        console.warn("Config data element not found");
        return;
    }

    try {
        const config = JSON.parse(configElement.textContent);
        const ruleName = ruleSelect.value;
        const rule = config.rules[ruleName];

        // Null-safe element access and setting
        const getOptionEl = document.getElementById('get_option');
        const actionOptionEl = document.getElementById('action_option');
        const keepWatchedEl = document.getElementById('keep_watched');
        const monitorWatchedEl = document.getElementById('monitor_watched');
        
        // keep_watched/monitor_watched are optional, opt-in fields - a rule
        // may not have them at all, which means "not managed" (blank/"").
        if (getOptionEl) getOptionEl.value = rule ? rule.get_option : '';
        if (actionOptionEl) actionOptionEl.value = rule ? rule.action_option : 'monitor';
        if (keepWatchedEl) keepWatchedEl.value = (rule && rule.keep_watched) ? rule.keep_watched : '';
        if (monitorWatchedEl) monitorWatchedEl.value = (rule && rule.monitor_watched !== undefined) ? rule.monitor_watched.toString() : '';
    } catch (error) {
        console.error("Error loading rule:", error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const ruleSelect = document.getElementById('rule_name');

    if (ruleSelect) {
        ruleSelect.addEventListener('change', loadRule);

        // Initial load
        loadRule();
    }
});

// Validate get_option/keep_watched before letting the rule form submit.
// get_option is required (it's what "fill ahead" always needs); keep_watched
// is optional/opt-in - blank just means "don't delete anything" - but if
// something IS entered, it must be 'season', 'all', or a whole number.
document.addEventListener('DOMContentLoaded', function() {
    const settingsForm = document.getElementById('settings-form');
    if (!settingsForm) return;

    const validPattern = /^(season|all|\d+)$/i;

    settingsForm.addEventListener('submit', function(e) {
        const getOption = document.getElementById('get_option');
        const keepWatched = document.getElementById('keep_watched');

        if (getOption && !validPattern.test(getOption.value.trim())) {
            e.preventDefault();
            alert(`"${getOption.value}" isn't valid for "${getOption.previousElementSibling.textContent}" - enter 'season', 'all', or a whole number.`);
            getOption.focus();
            return;
        }

        if (keepWatched && keepWatched.value.trim() && !validPattern.test(keepWatched.value.trim())) {
            e.preventDefault();
            alert(`"${keepWatched.value}" isn't valid for "${keepWatched.previousElementSibling.textContent}" - leave it blank, or enter 'season', 'all', or a whole number.`);
            keepWatched.focus();
            return;
        }
    });
});

function toggleNewRuleName() {
    const ruleSelect = document.getElementById('rule_name');
    const newRuleNameGroup = document.getElementById('new_rule_name_group');
    
    if (!ruleSelect || !newRuleNameGroup) {
        console.warn("Required elements not found");
        return;
    }
    
    if (ruleSelect.value === 'add_new') {
        newRuleNameGroup.style.display = 'block';
        
        // Reset form fields
        const fields = [
            'get_option', 
            'action_option', 
            'keep_watched', 
            'monitor_watched'
        ];
        
        fields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                if (fieldId === 'action_option') {
                    field.value = 'monitor';
                } else {
                    // keep_watched and monitor_watched default to "not
                    // managed" (blank) for a new rule - opt-in only.
                    field.value = '';
                }
            }
        });
    } else {
        newRuleNameGroup.style.display = 'none';
        loadRule();
    }
}

function confirmDeleteRule() {
    const ruleSelect = document.getElementById('rule_name');
    const deleteRuleInput = document.getElementById('delete_rule_name');
    
    if (ruleSelect.value === 'add_new') {
        alert('Cannot delete a new rule that hasn\'t been created yet.');
        return;
    }
    
    deleteRuleInput.value = ruleSelect.value;
    
    if (confirm(`Are you sure you want to delete the rule "${ruleSelect.value}"?`)) {
        document.getElementById('delete-rule-form').submit();
    }
}

function updateCheckboxes() {
    const ruleSelect = document.getElementById('assign_rule_name');
    const selectedRule = ruleSelect.value;
    
    document.querySelectorAll('.series-checkbox').forEach(checkbox => {
        // If the checkbox's current rule matches the selected rule, check it
        checkbox.checked = checkbox.dataset.rule === selectedRule;
    });
}

function adjustScrollableRows() {
    document.querySelectorAll('.scrollable-row').forEach(row => {
        // If the row has 6 or fewer items, add the 'few-items' class
        if (row.children.length <= 6) {
            row.classList.add('few-items');
        } else {
            row.classList.remove('few-items');
        }
    });
}

function loadPopularShows() {
    const container = document.getElementById('popular-shows-row');
    
    if (!container) {
        console.error('Popular shows container not found!');
        return;
    }
    
    console.log('Loading popular shows...');
    
    fetch('/api/tmdb/filtered/tv')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Popular shows data received:', data);
            container.innerHTML = ''; // Clear loading indicator
            
            const results = data.results || [];
            
            if (results.length === 0) {
                container.innerHTML = '<div class="loading-indicator">No popular shows available</div>';
                return;
            }
            
            results.forEach(item => {
                const mediaItem = createMediaItem({
                    id: item.id,
                    title: item.name,
                    posterUrl: item.posterUrl,
                    type: 'tv',
                    subtitle: item.releaseYear || '',
                    overview: item.overview || 'No description available',
                    hasDetails: true
                });
                
                container.appendChild(mediaItem);
            });
            
            // After adding content, check if we need to adjust the row
            adjustScrollableRows();
        })
        .catch(error => {
            console.error('Error loading popular shows:', error);
            container.innerHTML = '<div class="loading-indicator">Error loading content: ' + error.message + '</div>';
        });
}

function loadPopularMovies() {
    const container = document.getElementById('popular-movies-row');
    
    if (!container) {
        console.error('Popular movies container not found!');
        return;
    }
    
    console.log('Loading popular movies...');
    
    fetch('/api/tmdb/filtered/movies')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Popular movies data received:', data);
            container.innerHTML = ''; // Clear loading indicator
            
            const results = data.results || [];
            
            if (results.length === 0) {
                container.innerHTML = '<div class="loading-indicator">No popular movies available</div>';
                return;
            }
            
            results.forEach(item => {
                const mediaItem = createMediaItem({
                    id: item.id,
                    title: item.title,
                    posterUrl: item.posterUrl,
                    type: 'movie',
                    subtitle: item.releaseYear || '',
                    overview: item.overview || 'No description available',
                    hasDetails: true
                });
                
                container.appendChild(mediaItem);
            });
            
            // After adding content, check if we need to adjust the row
            adjustScrollableRows();
        })
        .catch(error => {
            console.error('Error loading popular movies:', error);
            container.innerHTML = '<div class="loading-indicator">Error loading content: ' + error.message + '</div>';
        });
}

function createMediaItem(data) {
    const mediaItem = document.createElement('div');
    mediaItem.className = 'media-item';
    mediaItem.dataset.id = data.id;
    mediaItem.dataset.type = data.type;
    
    const posterUrl = data.posterUrl || '/static/placeholder-banner.png';
    const subtitle = data.subtitle || '';
    
    // Create the HTML structure with or without details button
    if (data.hasDetails) {
        mediaItem.innerHTML = `
            <div class="poster-wrapper">
                <img src="${posterUrl}" alt="${data.title}" class="poster">
                <button class="details-button" aria-label="Show details">i</button>
                <div class="media-info">
                    <p class="media-subtitle">${subtitle}</p>
                </div>
            </div>
        `;
        
        // Add details button click handler
        const detailsButton = mediaItem.querySelector('.details-button');
        detailsButton.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent the poster click event
            showDetailsModal(data);
        });
    } else {
        mediaItem.innerHTML = `
            <div class="poster-wrapper">
                <img src="${posterUrl}" alt="${data.title}" class="poster">
                <div class="media-info">
                    <p class="media-subtitle">${subtitle}</p>
                </div>
            </div>
        `;
    }
    
    // Add poster click handler (separate from the details button)
    mediaItem.addEventListener('click', function() {
        if (data.hasDetails) {
            showDetailsModal(data);
        } else {
            // For existing content that doesn't need details button
            if (data.type === 'tv') {
                window.location.href = data.sonarr_series_url || `/select-episodes/${data.id}`;
            } else {
                requestMovie(data.id, data.title);
            }
        }
    });
    
    return mediaItem;
}

function showDetailsModal(data) {
    // Set modal content
    document.getElementById('detailsTitle').textContent = data.title;
    document.getElementById('detailsYear').textContent = data.subtitle;
    document.getElementById('detailsOverview').textContent = data.overview;
    document.getElementById('detailsPoster').src = data.posterUrl;
    
    // Clear previous footer buttons
    const modalFooter = document.getElementById('detailsModalFooter');
    modalFooter.innerHTML = '';
    
    // Get Jellyseerr URL from hidden input
    const jellyseerrUrlInput = document.getElementById('jellyseerr-url');
    const jellyseerrUrl = jellyseerrUrlInput ? jellyseerrUrlInput.value : '';

    if (data.type === 'movie') {
        // Request Movie button
        const requestBtn = document.createElement('button');
        requestBtn.className = 'btn btn-primary me-2';
        requestBtn.textContent = 'Request Movie';
        requestBtn.addEventListener('click', function() {
            $('#detailsModal').modal('hide');
            requestMovie(data.id, data.title);
        });
        modalFooter.appendChild(requestBtn);

        // Jellyseerr Link button
        const jellyseerrBtn = document.createElement('button');
        jellyseerrBtn.className = 'btn btn-secondary';
        jellyseerrBtn.textContent = 'View in Jellyseerr';
        jellyseerrBtn.addEventListener('click', function() {
            if (jellyseerrUrl) {
                window.open(`${jellyseerrUrl}`, '_blank');
            } else {
                alert('Jellyseerr URL is not configured.');
            }
        });
        modalFooter.appendChild(jellyseerrBtn);
    } else {
        // Request Show button
        const requestBtn = document.createElement('button');
        requestBtn.className = 'btn btn-primary me-2';
        requestBtn.textContent = 'Request Show';
        requestBtn.addEventListener('click', function() {
            $('#detailsModal').modal('hide');
            requestShow(data.id, data.title);
        });
        modalFooter.appendChild(requestBtn);

        /*
        // Pilot Only button
        const pilotBtn = document.createElement('button');
        pilotBtn.className = 'btn btn-secondary me-2';
        pilotBtn.textContent = 'Pilot Only';
        pilotBtn.addEventListener('click', function() {
            $('#detailsModal').modal('hide');
            fetch('/api/request/tv', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tmdbId: data.id,
                    check_existing: true,
                    create_season_request: true,
                    pilot: true
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Pilot request processed. Check requests section.');
                    window.location.href = '/?section=settings&subsection=requests_section';
                } else {
                    alert(`Error: ${data.error || 'Unknown error'}`);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('There was an error processing your request.');
            });
        });
        modalFooter.appendChild(pilotBtn);
        */

        // Jellyseerr Link button
        const jellyseerrBtn = document.createElement('button');
        jellyseerrBtn.className = 'btn btn-secondary';
        jellyseerrBtn.textContent = 'View in Jellyseerr';
        jellyseerrBtn.addEventListener('click', function() {
            if (jellyseerrUrl) {
                window.open(`${jellyseerrUrl}`, '_blank');
            } else {
                alert('Jellyseerr URL is not configured.');
            }
        });
        modalFooter.appendChild(jellyseerrBtn);
    }
    
    // Show the modal
    $('#detailsModal').modal('show');
}
// function to handle show requests
function requestShow(tmdbId, title) {
    fetch('/api/request/tv', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            tmdbId: tmdbId,
            check_existing: true,  // Add this parameter to check if series already exists
            create_season_request: true
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (data.exists) {
                alert(`Show "${title}" already exists. Check requests for season selection.`);
            } else {
                alert(`Show "${title}" added. Check requests for season selection.`);
            }
            window.location.href = '/?section=settings&subsection=requests_section';
        } else {
            alert(`Error: ${data.error || 'Unknown error'}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('There was an error processing your request.');
    });
}

function requestMovie(tmdbId, title) {
    if (confirm(`Would you like to request "${title}"?`)) {
        // Send request to your backend
        fetch('/api/radarr/request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tmdbId: tmdbId,
                title: title
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`"${title}" has been successfully requested!`);
            } else {
                alert(`Error requesting "${title}": ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('There was an error processing your request. Please try again later.');
        });
    }
}

function requestAllSeasons(tmdbId, title) {
    if (confirm(`Would you like to request all seasons of "${title}"?`)) {
        // Send request to your backend
        fetch('/api/request/tv', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tmdbId: tmdbId,
                seasons: ["all"],
                title: title
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`All seasons of "${title}" have been successfully requested!`);
            } else {
                alert(`Error requesting "${title}": ${data.message || data.error}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('There was an error processing your request. Please try again later.');
        });
    }
}

function showSection(sectionId) {
    // First, check if the section exists
    const element = document.getElementById(sectionId);
    
    if (!element) {
        console.error(`Error: Section with ID "${sectionId}" not found in the DOM`);
        return; // Exit early if element doesn't exist
    }
    
    // Check if it's a settings subsection
    if (element.classList.contains('settings-subsection')) {
        // It's a settings subsection
        
        // Make sure we're in the settings tab
        showMainTab('settings-tab');
        
        // Hide all other settings subsections
        document.querySelectorAll('.settings-subsection').forEach(section => {
            section.style.display = 'none';
        });
        
        // Show this settings subsection
        element.style.display = 'block';
    } else {
        // It's a main tab or something else
        document.querySelectorAll('.main-tab').forEach(tab => {
            tab.style.display = 'none';
        });
        
        // Show the requested section
        element.style.display = 'block';
    }
}

// Toggle request form fields based on selected type
function toggleRequestFields() {
    const requestType = document.getElementById('request_type').value;
    const seasonField = document.getElementById('season_field');
    const episodeField = document.getElementById('episode_field');
    const yearField = document.getElementById('year_field');
    
    if (requestType === 'tv_season') {
        seasonField.style.display = 'block';
        episodeField.style.display = 'none';
        yearField.style.display = 'none';
    } else if (requestType === 'tv_episode') {
        seasonField.style.display = 'block';
        episodeField.style.display = 'block';
        yearField.style.display = 'none';
    } else if (requestType === 'movie') {
        seasonField.style.display = 'none';
        episodeField.style.display = 'none';
        yearField.style.display = 'block';
    }
}
function scrollRowLeft(button) {
    const row = button.closest('.row-header').nextElementSibling;
    row.scrollBy({
        left: -300,
        behavior: 'smooth'
    });
}

function scrollRowRight(button) {
    const row = button.closest('.row-header').nextElementSibling;
    row.scrollBy({
        left: 300,
        behavior: 'smooth'
    });
}

window.addEventListener('DOMContentLoaded', (event) => {
    if (window.location.search.indexOf('message=') >= 0) {
        let clean_uri = window.location.protocol + "//" + window.location.host + window.location.pathname;
        window.history.replaceState({}, document.title, clean_uri);
    }
});