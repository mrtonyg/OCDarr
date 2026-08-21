// Service status used to be computed server-side in the / route on every
// page load (3 blocking HTTP calls with a 5s timeout each) - moved to a
// client-side fetch against /health so a slow/unreachable service doesn't
// hold up the whole dashboard render.
function loadServiceStatus() {
    const list = document.getElementById('service-status-list');
    if (!list) return;

    fetch('/health')
        .then(response => response.json())
        .then(data => {
            const services = data.services || {};
            list.innerHTML = Object.entries(services).map(([service, state]) => `
                <li class="mb-2">
                    <span class="badge ${state === 'Online' ? 'badge-success' : 'badge-danger'}" style="width: 10px; height: 10px; display: inline-block; border-radius: 50%; padding: 0; margin-right: 8px;"></span>
                    ${service.charAt(0).toUpperCase() + service.slice(1)}: ${state}
                </li>
            `).join('');
        })
        .catch(() => {
            list.innerHTML = '<li class="mb-2 text-muted">Unable to check service status.</li>';
        });
}

document.addEventListener('DOMContentLoaded', function() {
    loadServiceStatus();

    // Add event listeners for episode selection in requests section
    const selectAllButtons = document.querySelectorAll('.select-all');
    const selectNoneButtons = document.querySelectorAll('.select-none');
    const cancelRequestButtons = document.querySelectorAll('.cancel-request');

    // Set up URL parameters and tab selection
    const urlParams = new URLSearchParams(window.location.search);
    const sectionParam = urlParams.get('section');

    let tabToShow = 'dashboard-tab'; // Default

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
});
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
        // Fallback to the dashboard tab
        const dashboardTab = document.getElementById('dashboard-tab');
        if (dashboardTab) dashboardTab.style.display = 'block';
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

window.addEventListener('DOMContentLoaded', (event) => {
    if (window.location.search.indexOf('message=') >= 0) {
        let clean_uri = window.location.protocol + "//" + window.location.host + window.location.pathname;
        window.history.replaceState({}, document.title, clean_uri);
    }
});