// Profiles & highscores management for songs page
// Extracted from former inline <script> in songs.html to keep markup clean and reusable.
// This file is loaded globally; it initializes itself only when songs page elements are present.

(function(){
    // Cookie helpers (shared)
    function setCookie(name, value, days){
        try{
            const d = new Date();
            d.setTime(d.getTime() + (days*24*60*60*1000));
            document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/`;
        }catch(e){}
    }
    function getCookie(name){
        try{
            const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
            return match ? decodeURIComponent(match[1]) : null;
        }catch(e){ return null; }
    }
    function initProfilesOnSongsPage(){
    const selectEl = document.getElementById('profile_select');
    const inputEl = document.getElementById('profile_name_input');
        const msgEl = document.getElementById('profile_message');
        const createBtn = document.getElementById('create_profile_btn');

        // Guard: only run once per page load and only if songs profile UI exists
        if(!selectEl || !createBtn || createBtn.dataset.profilesInitialized === 'true'){ return; }
        createBtn.dataset.profilesInitialized = 'true';

        function showMsg(text, isError=false){
            if(!msgEl) return;
            msgEl.textContent = text || '';
            msgEl.classList.remove('text-red-400','text-teal-400');
            msgEl.classList.add(isError ? 'text-red-400' : 'text-teal-400');
        }

        function selectProfile(id, name){
            if(!id){ return; }
            window.currentProfileId = parseInt(id);
            setCookie('currentProfileId', window.currentProfileId, 365);
            // sync hidden native select value for compatibility
            if(selectEl){ selectEl.value = String(id); }
            fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
            showMsg('Selected profile: ' + name);
            if(typeof get_songs === 'function') get_songs();
        }

    function renderCustomDropdown(select, profiles, current){
            // ensure native select mirrors data but stays hidden
            select.innerHTML = '';
            profiles.forEach(p=>{
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                if(current && parseInt(current) === p.id) opt.selected = true;
                select.appendChild(opt);
            });
            select.classList.add('hidden');

            // Create container if missing
            let container = document.getElementById('profile_dropdown_container');
            if(!container){
                container = document.createElement('div');
                container.id = 'profile_dropdown_container';
                container.className = 'relative inline-block';
                // insert right after the select element
                select.parentElement.insertBefore(container, select.nextSibling);
            }
            container.innerHTML = '';

            const selectedProfile = profiles.find(p=> current && parseInt(current) === p.id) || profiles[0];

            // Toggle button
            const toggle = document.createElement('button');
            toggle.type = 'button';
            // Remove bg-* classes; we set background inline to control color precisely
            toggle.className = 'border border-gray-300 dark:border-gray-600 rounded px-3 py-2 text-sm text-gray-700 dark:text-gray-200 flex items-center justify-between text-left';
            // Make the toggle wider so long names fit comfortably next to the ×
            toggle.style.minWidth = '280px';
            // Theme-applier: gray in both themes (light gray in light, dark gray in dark)
            const applyDropdownTheme = () => {
                const isDark = document.documentElement.classList.contains('dark');
                toggle.style.backgroundColor = isDark ? '#374151' : '#e5e7eb'; // gray-700 / gray-200
                toggle.style.opacity = '1';
                toggle.style.backdropFilter = 'none';
            };
            toggle.innerHTML = `<span class="truncate flex-1 min-w-0 mr-2 text-left" title="${selectedProfile ? selectedProfile.name : ''}">${selectedProfile ? selectedProfile.name : 'Select profile'}</span>
                                <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>`;
            container.appendChild(toggle);

            // Dropdown menu
            const menu = document.createElement('div');
            // Remove bg-* classes; we set background inline to control color precisely
            menu.className = 'absolute z-10 mt-1 w-full max-h-60 overflow-auto border border-gray-300 dark:border-gray-600 rounded shadow-lg hidden text-left';
            // Match minimum width with toggle so text has room and doesn’t sit under the ×
            menu.style.minWidth = '280px';
            const applyMenuTheme = () => {
                const isDark = document.documentElement.classList.contains('dark');
                menu.style.backgroundColor = isDark ? '#374151' : '#e5e7eb'; // gray-700 / gray-200
                menu.style.opacity = '1';
                menu.style.backdropFilter = 'none';
            };
            profiles.forEach(p=>{
                const row = document.createElement('div');
                row.className = 'flex items-center justify-between px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:glass-light cursor-pointer text-left transition-smooth-fast';
                const nameSpan = document.createElement('span');
                // Let the name take available space and truncate before the delete button; keep left aligned
                nameSpan.className = 'truncate flex-1 min-w-0 pr-3 text-left';
                nameSpan.textContent = p.name;
                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.title = 'Delete profile';
                delBtn.className = 'text-red-500 hover:text-red-600 pl-2 pr-1';
                delBtn.textContent = '×';

                // Select on row click (except delete)
                row.addEventListener('click', (e)=>{
                    // ignore if delete button clicked
                    if(e.target === delBtn) return;
                    menu.classList.add('hidden');
                    selectProfile(p.id, p.name);
                    toggle.querySelector('span').textContent = p.name;
                });

                // Delete handler
                delBtn.addEventListener('click', (e)=>{
                    e.stopPropagation();
                    const confirmMsg = `Delete profile \"${p.name}\"? This will remove highscores for this profile.`;
                    if(typeof showConfirm === 'function') {
                        showConfirm(confirmMsg, function() {
                            fetch('/api/delete_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: p.id})})
                                .then(r=>r.json())
                                .then(resp=>{
                                    if(resp.success){
                                        showMsg('Profile deleted');
                                        if(window.currentProfileId == p.id){ window.currentProfileId = null; }
                                        loadProfiles();
                                        if(typeof get_songs === 'function') get_songs();
                                    } else {
                                        showMsg(resp.error || 'Failed to delete profile', true);
                                    }
                                })
                                .catch(()=>showMsg('Network error deleting profile', true));
                        });
                    } else {
                        if(!window.confirm(confirmMsg)) return;
                        fetch('/api/delete_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: p.id})})
                            .then(r=>r.json())
                            .then(resp=>{
                                if(resp.success){
                                    showMsg('Profile deleted');
                                    if(window.currentProfileId == p.id){ window.currentProfileId = null; }
                                    loadProfiles();
                                    if(typeof get_songs === 'function') get_songs();
                                } else {
                                    showMsg(resp.error || 'Failed to delete profile', true);
                                }
                            })
                            .catch(()=>showMsg('Network error deleting profile', true));
                    }
                });

                row.appendChild(nameSpan);
                row.appendChild(delBtn);
                menu.appendChild(row);
            });
            container.appendChild(menu);

            // Apply initial theme and keep in sync with theme toggles
            applyDropdownTheme();
            applyMenuTheme();
            const themeObserver = new MutationObserver(() => { applyDropdownTheme(); applyMenuTheme(); });
            themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

            // Toggle open/close
            toggle.addEventListener('click', ()=>{
                menu.classList.toggle('hidden');
            });
            // Close on outside click
            document.addEventListener('click', (e)=>{
                if(!container.contains(e.target)){
                    menu.classList.add('hidden');
                }
            });
        }

    function loadProfiles(){
            fetch('/api/get_profiles')
                .then(r=>r.json())
                .then(data=>{
            let current = window.currentProfileId || getCookie('currentProfileId');
                    const profiles = data.profiles || [];
                    if(profiles.length === 0){
                        selectEl.innerHTML = '';
                        const opt = document.createElement('option');
                        opt.textContent = 'No profiles';
                        opt.value='';
                        selectEl.appendChild(opt);
                        showMsg('Create a profile to start tracking highscores.');
                        return;
                    }
                    renderCustomDropdown(selectEl, profiles, current);
                    if(current && profiles.some(p=>p.id === parseInt(current))){
                        window.currentProfileId = parseInt(current);
                        setCookie('currentProfileId', window.currentProfileId, 365);
                        fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                        if(typeof get_songs === 'function') get_songs();
                    } else if(!window.currentProfileId && profiles[0]){
                        window.currentProfileId = profiles[0].id;
                        setCookie('currentProfileId', window.currentProfileId, 365);
                        fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                        if(typeof get_songs === 'function') get_songs();
                    }
                    showMsg('Profiles loaded');
                })
                .catch(()=>showMsg('Failed to load profiles', true));
        }

        function createProfile(){
            const name = (inputEl.value || '').trim();
            if(!name){
                showMsg('Enter a profile name', true);
                inputEl.focus();
                return;
            }
            fetch('/api/create_profile', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({name})
            }).then(r=>r.json())
              .then(resp=>{
                  if(resp.success){
                      window.currentProfileId = resp.profile.id;
                      setCookie('currentProfileId', window.currentProfileId, 365);
                      showMsg('Profile created');
                      inputEl.value='';
                      // Sync selection to backend
                      fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                      loadProfiles();
                      if(typeof get_songs === 'function') get_songs();
                  } else {
                      showMsg(resp.error || 'Error creating profile', true);
                  }
              })
              .catch(()=>showMsg('Network error creating profile', true));
        }

        // Expose for other scripts if needed
        window.loadProfiles = loadProfiles;
        window.createProfile = createProfile;

        createBtn.addEventListener('click', createProfile);
        inputEl.addEventListener('keyup', (e)=>{ if(e.key==='Enter'){ createProfile(); }});
        selectEl.addEventListener('change', function(){
            window.currentProfileId = this.value || null;
            if(window.currentProfileId){ setCookie('currentProfileId', window.currentProfileId, 365); }
            // Sync selection to backend (null or id)
            fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
            if(this.value){
                showMsg('Selected profile: ' + this.options[this.selectedIndex].text);
                if(typeof get_songs === 'function') get_songs();
            }
        });

    // Slightly widen the name input so longer names are visible and not cramped
    if(inputEl){ inputEl.style.minWidth = '280px'; }
    loadProfiles();
    }

    // Run after each dynamic page load (index.js calls initialize_songs which will invoke this)
    window.initProfilesOnSongsPage = initProfilesOnSongsPage;

    // Also attempt immediate init in case songs page is the initial load
    if(document.readyState === 'loading'){
        document.addEventListener('DOMContentLoaded', initProfilesOnSongsPage);
    } else {
        initProfilesOnSongsPage();
    }
})();
// profiles.js - handles user profiles and highscores on songs page
(function(){
    console.log('[Profiles] profiles.js loaded');
    const state = {
        selectEl: null,
        inputEl: null,
        msgEl: null,
        createBtn: null
    };

    function showMsg(text, isError=false){
        if(!state.msgEl) return;
        state.msgEl.textContent = text || '';
        state.msgEl.classList.remove('text-red-400','text-teal-400');
        state.msgEl.classList.add(isError ? 'text-red-400' : 'text-teal-400');
    }

    function loadProfiles(){
        if(!state.selectEl){
            console.warn('[Profiles] loadProfiles called before init');
            return;
        }
        fetch('/api/get_profiles')
            .then(r=>r.json())
            .then(data=>{
                const current = window.currentProfileId;
                const profiles = data.profiles || [];
                if(profiles.length === 0){
                    state.selectEl.innerHTML = '';
                    const opt = document.createElement('option');
                    opt.textContent = 'No profiles';
                    opt.value='';
                    state.selectEl.appendChild(opt);
                    showMsg('Create a profile to start tracking highscores.');
                    return;
                }
                // Reuse renderer from the other IIFE if present
                if(typeof window.loadProfiles === 'function'){
                    // call the other loader to render deletes UI too
                    try { window.loadProfiles(); return; } catch(e) {}
                }
                // Basic fallback
                state.selectEl.innerHTML = '';
                profiles.forEach(p=>{
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.name;
                    if(current && parseInt(current) === p.id) opt.selected = true;
                    state.selectEl.appendChild(opt);
                });
                let cookieCurrent = window.currentProfileId || getCookie('currentProfileId');
                if(cookieCurrent && profiles.some(p=>p.id === parseInt(cookieCurrent))){
                    window.currentProfileId = parseInt(cookieCurrent);
                    setCookie('currentProfileId', window.currentProfileId, 365);
                    fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                } else if(!window.currentProfileId && profiles[0]){
                    window.currentProfileId = profiles[0].id;
                    setCookie('currentProfileId', window.currentProfileId, 365);
                    fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                }
                showMsg('Profiles loaded');
            })
            .catch(()=>showMsg('Failed to load profiles', true));
    }

    function createProfile(){
        console.log('[Profiles] createProfile invoked');
        const name = (state.inputEl && state.inputEl.value || '').trim();
        if(!name){
            showMsg('Enter a profile name', true);
            state.inputEl && state.inputEl.focus();
            return;
        }
        fetch('/api/create_profile', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({name})
        }).then(r=>r.json())
          .then(resp=>{
              if(resp.success){
                  window.currentProfileId = resp.profile.id;
                  setCookie('currentProfileId', window.currentProfileId, 365);
                  showMsg('Profile created');
                  if(state.inputEl) state.inputEl.value='';
                  fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                  loadProfiles();
                  if(typeof get_songs === 'function') get_songs();
              } else {
                  showMsg(resp.error || 'Error creating profile', true);
              }
          })
          .catch(()=>showMsg('Network error creating profile', true));
    }

    function attachEvents(){
        if(state.createBtn){
            state.createBtn.addEventListener('click', createProfile);
        }
        if(state.inputEl){
            state.inputEl.addEventListener('keyup', e=>{ if(e.key==='Enter') createProfile(); });
        }
        if(state.selectEl){
            state.selectEl.addEventListener('change', function(){
                window.currentProfileId = this.value || null;
                if(window.currentProfileId){ setCookie('currentProfileId', window.currentProfileId, 365); }
                fetch('/api/set_current_profile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile_id: window.currentProfileId})}).catch(()=>{});
                if(this.value){
                    showMsg('Selected profile: ' + this.options[this.selectedIndex].text);
                    if(typeof get_songs === 'function') get_songs();
                }
            });
        }
    }

    function init(){
        state.selectEl = document.getElementById('profile_select');
        state.inputEl = document.getElementById('profile_name_input');
        state.msgEl = document.getElementById('profile_message');
        state.createBtn = document.getElementById('create_profile_btn');
        if(!state.selectEl || !state.createBtn){
            console.warn('[Profiles] Elements not found on this page; init skipped');
            return;
        }
        attachEvents();
    // Keep input reasonably wide here as well (fallback path)
    if(state.inputEl){ state.inputEl.style.minWidth = '280px'; }
    loadProfiles();
        console.log('[Profiles] Init complete');
    }

    if(document.readyState === 'loading'){
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window._profiles = {
        createProfile,
        loadProfiles
    };
})();
