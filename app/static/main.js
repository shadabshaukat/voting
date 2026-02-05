// Helper to fetch JSON with error handling
async function fetchJSON(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`Error ${resp.status}: ${err}`);
    }
    return await resp.json();
}

// ----- Offline queue + toast helpers -----
const VOTE_QUEUE_KEY = 'offlineVoteQueue';

function showToast(message, type = 'info', timeout = 2500) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', type === 'warn' ? 'assertive' : 'polite');
    el.textContent = message;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 250);
    }, timeout);
}

function loadQueue() {
    try {
        const raw = localStorage.getItem(VOTE_QUEUE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveQueue(arr) {
    try { localStorage.setItem(VOTE_QUEUE_KEY, JSON.stringify(arr)); } catch {}
}

async function registerBackgroundSync() {
    if (!('serviceWorker' in navigator)) return;
    try {
        const reg = await navigator.serviceWorker.ready;
        if ('sync' in reg) await reg.sync.register('flushVotes');
    } catch {}
}

async function flushQueue() {
    const q = loadQueue();
    if (!q.length) return 0;
    let success = 0;
    const remaining = [];
    for (const item of q) {
        try {
            await fetchJSON(`/poll/${item.pollId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item.payload),
            });
            success++;
        } catch {
            remaining.push(item);
        }
    }
    saveQueue(remaining);
    return success;
}

function enqueueVote(pollId, payload) {
    const q = loadQueue();
    q.push({ pollId, payload, ts: Date.now() });
    saveQueue(q);
    registerBackgroundSync();
}

// Status helpers for friendly closed messaging
function typeLabel(t) {
    if (t === 'survey') return 'Survey';
    if (t === 'poll') return 'Poll';
    return 'Trivia';
}
function renderClosedMessage(container, status) {
    const lbl = typeLabel(status.poll_type || 'trivia');
    const title = status.title || 'Event';
    const p = document.createElement('p');
    p.textContent = `${lbl} closed: ${title}`;
    container.innerHTML = '';
    container.appendChild(p);
}
async function getStatusBySlug(slug) {
    return await fetchJSON(`/poll/status/by-slug?slug=${encodeURIComponent(slug)}`);
}
async function getStatusByTitle(title) {
    return await fetchJSON(`/poll/status/by-title?title=${encodeURIComponent(title)}`);
}

// ---------- PARTICIPANT POPUP ----------
function showParticipantModal(pollId) {
    // Immediately remove entry modal to avoid any stray submit triggering navigation
    const entry = document.getElementById('entry-modal');
    if (entry) {
        entry.style.display = 'none';
        if (entry.parentNode) entry.parentNode.removeChild(entry);
    }
    const modal = document.getElementById('participant-modal');
    modal.style.display = 'block';
    const nameInput = document.getElementById('participant-name');
    if (nameInput) nameInput.focus();
    const form = document.getElementById('participant-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const name = form.elements['name'].value.trim();
        const company = form.elements['company'].value.trim();
        if (!name) {
            alert('Name is required');
            return false;
        }
        try {
            await startPoll(pollId, { name, company });
            modal.style.display = 'none';
            return false;
        } catch (err) {
            console.error(err);
            alert('Could not start the poll. It may no longer be active.');
            sessionStorage.removeItem('selectedPollId');
            return false;
        }
    };
}

// ---------- POLL LOGIC ----------
let pollTimer = null;

async function startPoll(pollId, participant) {
    const pollData = await fetchJSON(`/poll/${pollId}`);
    const container = document.getElementById('poll-container');
    // Render title & description safely
    container.innerHTML = '';
    const h2 = document.createElement('h2');
    h2.textContent = pollData.title || '';
    container.appendChild(h2);
    if (pollData.description) {
        const p = document.createElement('p');
        p.textContent = pollData.description;
        container.appendChild(p);
    }
    // Remove entry modal completely to prevent reappearance
    const entry = document.getElementById('entry-modal');
    if (entry && entry.parentNode) entry.parentNode.removeChild(entry);

    const form = document.createElement('form');
    form.id = 'vote-form';

    pollData.questions.forEach((q, idx) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'question';
        qDiv.setAttribute('data-qid', String(q.id));
        const qp = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = `${idx + 1}. ${q.text}`;
        qp.appendChild(strong);
        qDiv.appendChild(qp);
        q.choices.forEach((c) => {
            const label = document.createElement('label');
            label.className = 'option-line';
            label.innerHTML = `
                <input type="radio" name="q_${q.id}" value="${c.id}" required>
                <span class="option-text"></span>
            `;
            label.querySelector('.option-text').textContent = c.text;
            qDiv.appendChild(label);
        });
        form.appendChild(qDiv);
    });

    const submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.textContent = 'Submit';
    form.appendChild(submitBtn);
    container.appendChild(form);

    // Timer (if poll has end_time)
    if (pollData.end_time) {
        const end = new Date(pollData.end_time);
        const now = new Date();
        let remaining = Math.max(0, Math.floor((end - now) / 1000));
        const timerEl = document.createElement('div');
        timerEl.id = 'timer';
        timerEl.setAttribute('role', 'timer');
        timerEl.setAttribute('aria-live', 'off');
        container.appendChild(timerEl);
        function format(sec) {
            const m = Math.floor(sec / 60);
            const s = sec % 60;
            return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
        }
        function renderTimer() {
            const txt = `${format(remaining)}`;
            timerEl.textContent = txt;
            timerEl.setAttribute('aria-label', `Time remaining: ${txt}`);
        }
        renderTimer();
        pollTimer = setInterval(() => {
            remaining--;
            renderTimer();
            if (remaining <= 0) {
                clearInterval(pollTimer);
                form.dispatchEvent(new Event('submit'));
            }
        }, 1000);
    }

    // Gentle validation highlight + submit flow
    form.addEventListener('change', (e) => {
        const target = e.target;
        if (target && target.matches('input[type="radio"][name^="q_"]')) {
            const qEl = target.closest('.question');
            if (qEl) qEl.classList.remove('invalid-block');
        }
    });

    let isSubmitting = false;
    form.onsubmit = async (e) => {
        e.preventDefault();
        if (isSubmitting) return;
        isSubmitting = true;
        if (pollTimer) clearInterval(pollTimer);

        // Validate all questions answered
        form.querySelectorAll('.question.invalid-block').forEach(el => el.classList.remove('invalid-block'));
        let firstMissing = null;
        const votes = [];
        pollData.questions.forEach((q) => {
            const checked = form.querySelector(`input[name="q_${q.id}"]:checked`);
            const qDiv = form.querySelector(`.question[data-qid="${q.id}"]`);
            if (!checked) {
                if (!firstMissing) firstMissing = qDiv;
                if (qDiv) qDiv.classList.add('invalid-block');
            } else {
                votes.push({ question_id: q.id, choice_id: parseInt(checked.value) });
            }
        });
        if (firstMissing) {
            firstMissing.scrollIntoView({ behavior: 'smooth', block: 'center' });
            isSubmitting = false;
            return;
        }

        const payload = { participant, votes };
        const localSubmitBtn = form.querySelector('button[type="submit"]');
        if (localSubmitBtn) { localSubmitBtn.disabled = true; localSubmitBtn.textContent = 'Submitting...'; }
        try {
            await fetchJSON(`/poll/${pollId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            sessionStorage.removeItem('selectedPollId');
            const thanks = document.createElement('div');
            const p = document.createElement('p');
            p.textContent = 'Thank you for voting!';
            const back = document.createElement('button');
            back.type = 'button';
            back.textContent = 'Return to start';
            back.addEventListener('click', () => {
                sessionStorage.removeItem('selectedPollId');
                location.href = '/';
            });
            thanks.appendChild(p);
            thanks.appendChild(back);
            container.innerHTML = '';
            container.appendChild(thanks);
        } catch (err) {
            // Offline or network error: queue it and inform the user
            const offlineLikely = !navigator.onLine || /Failed to fetch|NetworkError/i.test(err.message || '');
            if (offlineLikely) {
                enqueueVote(pollId, payload);
                showToast('You are offline. Your vote was saved and will be sent when online.', 'warn');
                sessionStorage.removeItem('selectedPollId');
                const queued = document.createElement('div');
                const p = document.createElement('p');
                p.textContent = 'Thanks! Your vote is queued and will be submitted automatically when back online.';
                const back = document.createElement('button');
                back.type = 'button';
                back.textContent = 'Return to start';
                back.addEventListener('click', () => {
                    sessionStorage.removeItem('selectedPollId');
                    location.href = '/';
                });
                queued.appendChild(p);
                queued.appendChild(back);
                container.innerHTML = '';
                container.appendChild(queued);
                registerBackgroundSync();
            } else {
                alert('Submission failed: ' + err.message);
                if (localSubmitBtn) { localSubmitBtn.disabled = false; localSubmitBtn.textContent = 'Submit'; }
                isSubmitting = false;
                return;
            }
        }
        isSubmitting = false;
    };
}

// ---------- INITIAL LOAD WITH ENTRY MODAL (type + join by) ----------
async function findPollIdByEntry(type, mode, value) {
    if (mode === 'active') {
        const list = await fetchJSON(`/poll/active?type=${encodeURIComponent(type)}`);
        if (!list || list.length === 0) throw new Error('No active items for selected type');
        return list[0].id;
    }
    if (mode === 'title') {
        const res = await fetchJSON(`/poll/by-title?title=${encodeURIComponent(value)}&type=${encodeURIComponent(type)}`);
        return res.id;
    }
    if (mode === 'slug') {
        const res = await fetchJSON(`/poll/by-slug?slug=${encodeURIComponent(value)}&type=${encodeURIComponent(type)}`);
        return res.id;
    }
    throw new Error('Invalid mode');
}

function currentPathSlug() {
    const path = location.pathname.replace(/^\/+/, '');
    if (!path) return null;
    if (/^[a-z0-9-]{5,20}$/.test(path)) return path;
    return null;
}

document.addEventListener('DOMContentLoaded', () => {
    // PWA install prompt wiring (optional button)
    let deferredPrompt = null;
    const installBtn = document.getElementById('install-btn');
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        if (installBtn) installBtn.style.display = 'inline-block';
    });
    if (installBtn) {
        installBtn.addEventListener('click', async () => {
            if (!deferredPrompt) return;
            installBtn.disabled = true;
            try {
                deferredPrompt.prompt();
                await deferredPrompt.userChoice;
                installBtn.style.display = 'none';
            } finally {
                installBtn.disabled = false;
                deferredPrompt = null;
            }
        });
    }

    const container = document.getElementById('poll-container');
    const modal = document.getElementById('entry-modal');
    const form = document.getElementById('entry-form');
    const typeSelect = document.getElementById('entry-type');
    const modeSelect = document.getElementById('entry-mode');
    const valueWrap = document.getElementById('entry-value-wrap');
    const valueInput = document.getElementById('entry-value');
    const valueLabel = document.getElementById('entry-value-label');

    function updateValueVisibility() {
        const mode = modeSelect.value;
        const show = mode !== 'active';
        valueWrap.style.display = show ? 'block' : 'none';
        valueWrap.setAttribute('aria-hidden', show ? 'false' : 'true');
        valueLabel.textContent = mode === 'title' ? 'Title' : 'Code';
        valueInput.placeholder = mode === 'title' ? 'Enter title' : 'Enter code';
    }

    modeSelect.addEventListener('change', updateValueVisibility);
    updateValueVisibility();

    // Suppress Enter submitting forms unexpectedly in modals
    [modal, document.getElementById('participant-modal')].forEach(m => {
        if (!m) return;
        m.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    const savedId = sessionStorage.getItem('selectedPollId');
    if (savedId) {
        if (modal) modal.style.display = 'none';
        showParticipantModal(parseInt(savedId, 10));
        return;
    }

    // Auto-join by URL slug
    const pathSlug = currentPathSlug();
    if (pathSlug) {
        (async () => {
            try {
                const types = ['trivia','survey','poll'];
                for (const t of types) {
                    try {
                        const res = await fetchJSON(`/poll/by-slug?slug=${encodeURIComponent(pathSlug)}&type=${encodeURIComponent(t)}`);
                        if (res && res.id) {
                            sessionStorage.setItem('selectedPollId', String(res.id));
                            if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
                            showParticipantModal(res.id);
                            return;
                        }
                    } catch (_) { /* continue */ }
                }
                container.textContent = 'No active session found for this link.';
            } catch (err) {
                try {
                    const st = await getStatusBySlug(pathSlug);
                    if (st && st.exists && (!st.is_active || st.archived)) {
                        renderClosedMessage(container, st);
                    } else {
                        container.textContent = 'No active session found for this link.';
                    }
                } catch (_) {
                    container.textContent = 'No active session found for this link.';
                }
            }
        })();
        return;
    }

    if (modal) modal.style.display = 'block';

    form.onsubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const type = typeSelect.value;
        const mode = modeSelect.value;
        const value = (valueInput.value || '').trim();
        if (mode !== 'active' && !value) {
            alert('Please provide a value for the selected join method.');
            return false;
        }
        try {
            const pollId = await findPollIdByEntry(type, mode, value);
            sessionStorage.setItem('selectedPollId', String(pollId));
            if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
            showParticipantModal(pollId);
            return false;
        } catch (err) {
            console.error(err);
            try {
                const modeIsTitle = mode === 'title';
                const status = modeIsTitle ? await getStatusByTitle(value) : await getStatusBySlug(value);
                if (status && status.exists && (!status.is_active || status.archived)) {
                    renderClosedMessage(container, status);
                } else {
                    container.textContent = 'No active session found for the selected type. Please check the title/code, or try again when the session is active.';
                }
            } catch (_) {
                container.textContent = 'No active session found for the selected type. Please check the title/code, or try again when the session is active.';
            }
            alert('No active session found.');
            return false;
        }
    };

    // Online/offline toasts and auto-flush
    window.addEventListener('online', async () => {
        showToast('Back online. Syncing any queued votes...', 'success');
        const sent = await flushQueue();
        if (sent > 0) showToast(`Sent ${sent} queued vote(s).`, 'success');
    });
    window.addEventListener('offline', () => showToast('Offline. Submissions will be queued.', 'warn'));

    // Listen for SW background sync messages
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('message', async (event) => {
            const { type } = event.data || {};
            if (type === 'flushVotes') {
                const sent = await flushQueue();
                if (sent > 0) showToast(`Sent ${sent} queued vote(s).`, 'success');
            }
        });
    }
});
// Helper to fetch JSON with error handling
async function fetchJSON(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`Error ${resp.status}: ${err}`);
    }
    return await resp.json();
}

// ----- Offline queue + toast helpers -----
const VOTE_QUEUE_KEY = 'offlineVoteQueue';

function showToast(message, type = 'info', timeout = 2500) {
    let el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', type === 'warn' ? 'assertive' : 'polite');
    el.textContent = message;
    document.body.appendChild(el);
    // Allow style to apply before showing
    requestAnimationFrame(() => {
        el.classList.add('show');
    });
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 250);
    }, timeout);
}

function loadQueue() {
    try {
        const raw = localStorage.getItem(VOTE_QUEUE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveQueue(arr) {
    try {
        localStorage.setItem(VOTE_QUEUE_KEY, JSON.stringify(arr));
    } catch {}
}

async function registerBackgroundSync() {
    if (!('serviceWorker' in navigator)) return;
    try {
        const reg = await navigator.serviceWorker.ready;
        if ('sync' in reg) {
            await reg.sync.register('flushVotes');
        }
    } catch {}
}

async function flushQueue() {
    const q = loadQueue();
    if (!q.length) return 0;
    let success = 0;
    const remaining = [];
    for (const item of q) {
        try {
            await fetchJSON(`/poll/${item.pollId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item.payload),
            });
            success++;
        } catch (e) {
            // Keep in queue if still failing
            remaining.push(item);
        }
    }
    saveQueue(remaining);
    return success;
}

function enqueueVote(pollId, payload) {
    const q = loadQueue();
    q.push({ pollId, payload, ts: Date.now() });
    saveQueue(q);
    registerBackgroundSync();
}

// Status helpers for friendly closed messaging
function typeLabel(t) {
    if (t === 'survey') return 'Survey';
    if (t === 'poll') return 'Poll';
    return 'Trivia';
}
function renderClosedMessage(container, status) {
    const lbl = typeLabel(status.poll_type || 'trivia');
    const title = status.title || 'Event';
    container.innerHTML = `<p>${lbl} closed: ${title}</p>`;
}
async function getStatusBySlug(slug) {
    return await fetchJSON(`/poll/status/by-slug?slug=${encodeURIComponent(slug)}`);
}
async function getStatusByTitle(title) {
    return await fetchJSON(`/poll/status/by-title?title=${encodeURIComponent(title)}`);
}

// ---------- PARTICIPANT POPUP ----------
function showParticipantModal(pollId) {
    // Immediately remove entry modal to avoid any stray submit triggering navigation
    const entry = document.getElementById('entry-modal');
    if (entry) {
        entry.style.display = 'none';
        if (entry.parentNode) entry.parentNode.removeChild(entry);
    }
    const modal = document.getElementById('participant-modal');
    modal.style.display = 'block';
    const form = document.getElementById('participant-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const name = form.elements['name'].value.trim();
        const company = form.elements['company'].value.trim();
        if (!name) {
            alert('Name is required');
            return false;
        }
        try {
            await startPoll(pollId, { name, company });
            // Only hide the modal after successful render
            modal.style.display = 'none';
            return false;
        } catch (err) {
            console.error(err);
            alert('Could not start the poll. It may no longer be active.');
            // Ensure entry can be retried
            sessionStorage.removeItem('selectedPollId');
            return false;
        }
    };
}

// ---------- POLL LOGIC ----------
let pollTimer = null;

async function startPoll(pollId, participant) {
    const pollData = await fetchJSON(`/poll/${pollId}`);
    const container = document.getElementById('poll-container');
    container.innerHTML = `<h2>${pollData.title}</h2><p>${pollData.description || ''}</p>`;
    // Hard-hide and remove entry modal to prevent reappearance
    const entry = document.getElementById('entry-modal');
    if (entry) {
        entry.style.display = 'none';
        if (entry.parentNode) entry.parentNode.removeChild(entry);
    }

    const form = document.createElement('form');
    form.id = 'vote-form';

    pollData.questions.forEach((q, idx) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'question';
        qDiv.innerHTML = `<p><strong>${idx + 1}. ${q.text}</strong></p>`;
        q.choices.forEach((c) => {
            const label = document.createElement('label');
            label.className = 'option-line';
            label.innerHTML = `
                <input type="radio" name="q_${q.id}" value="${c.id}" required>
                <span class="option-text">${c.text}</span>
            `;
            qDiv.appendChild(label);
        });
        form.appendChild(qDiv);
    });

    const submitBtn = document.createElement('button');
    submitBtn.type = 'submit';
    submitBtn.textContent = 'Submit';
    form.appendChild(submitBtn);
    container.appendChild(form);

    // Timer (if poll has end_time)
    if (pollData.end_time) {
        const end = new Date(pollData.end_time);
        const now = new Date();
        let remaining = Math.max(0, Math.floor((end - now) / 1000));
        const timerEl = document.createElement('div');
        timerEl.id = 'timer';
        container.appendChild(timerEl);
        function format(ms) {
            const m = Math.floor(ms / 60);
            const s = ms % 60;
            return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
        }
        function renderTimer() {
            timerEl.innerHTML = `<span class="clock"></span> ${format(remaining)}`;
        }
        renderTimer();
        pollTimer = setInterval(() => {
    let isSubmitting = false;
            renderTimer();
            if (remaining <= 0) {
                clearInterval(pollTimer);
                form.dispatchEvent(new Event('submit'));
            }
        }, 1000);
    }

    form.onsubmit = async (e) => {
        e.preventDefault();
        if (pollTimer) clearInterval(pollTimer);
        const votes = [];
        pollData.questions.forEach((q) => {
            const choiceInput = form[`q_${q.id}`];
            if (!choiceInput) return;
            const choiceId = choiceInput.value;
            votes.push({ question_id: q.id, choice_id: parseInt(choiceId) });
        });
        const payload = { participant, votes };
        try {
            await fetchJSON(`/poll/${pollId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            // Clear saved selection after successful submission
            const thanks = document.createElement('div');
            const p = document.createElement('p');
            p.textContent = 'Thank you for voting!';
            const back = document.createElement('button');
            back.type = 'button';
            back.textContent = 'Return to start';
            back.addEventListener('click', () => {
                sessionStorage.removeItem('selectedPollId');
                location.href = '/';
            });
            thanks.appendChild(p);
            thanks.appendChild(back);
            container.innerHTML = '';
            container.appendChild(thanks);
            container.innerHTML = '<p>Thank you for voting!</p>';
            // Network/offline handling: queue and confirm to user
            const offlineLikely = !navigator.onLine || /Failed to fetch|NetworkError/i.test(err.message);
            if (offlineLikely) {
                enqueueVote(pollId, payload);
                showToast('You are offline. Your vote was saved and will be sent when online.', 'warn');
                sessionStorage.removeItem('selectedPollId');
                const thanks = document.createElement('div');
                const p = document.createElement('p');
                p.textContent = 'Thanks! Your vote is queued and will be submitted automatically when back online.';
                const back = document.createElement('button');
                back.type = 'button';
                back.textContent = 'Return to start';
                back.addEventListener('click', () => {
                    sessionStorage.removeItem('selectedPollId');
                    location.href = '/';
                });
                thanks.appendChild(p);
                thanks.appendChild(back);
                container.innerHTML = '';
                container.appendChild(thanks);
                // Try to flush immediately if connection resumes quickly
                registerBackgroundSync();
            } else {
                alert('Submission failed: ' + err.message);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
                }
                isSubmitting = false;
                return;
            }
            alert('Submission failed: ' + err.message);
        }
    };
}

// ---------- INITIAL LOAD WITH ENTRY MODAL (type + join by) ----------
async function findPollIdByEntry(type, mode, value) {
    if (mode === 'active') {
        const list = await fetchJSON(`/poll/active?type=${encodeURIComponent(type)}`);
        if (!list || list.length === 0) throw new Error('No active items for selected type');
        return list[0].id;
    }
    if (mode === 'title') {
        const res = await fetchJSON(`/poll/by-title?title=${encodeURIComponent(value)}&type=${encodeURIComponent(type)}`);
        return res.id;
    }
    if (mode === 'slug') {
        const res = await fetchJSON(`/poll/by-slug?slug=${encodeURIComponent(value)}&type=${encodeURIComponent(type)}`);
        return res.id;
    }
    throw new Error('Invalid mode');
}

function currentPathSlug() {
    const path = location.pathname.replace(/^\/+/, '');
    if (!path) return null;
    // only accept simple 5-20 char lowercase/digit codes to avoid conflicts
    if (/^[a-z0-9-]{5,20}$/.test(path)) return path;
    return null;
}

document.addEventListener('DOMContentLoaded', () => {
    // Remove global capture suppression so JS handlers can run normally
    // (We still stop propagation in specific handlers.)
    const container = document.getElementById('poll-container');
    const modal = document.getElementById('entry-modal');
    const form = document.getElementById('entry-form');
    const typeSelect = document.getElementById('entry-type');
    const modeSelect = document.getElementById('entry-mode');
    const valueWrap = document.getElementById('entry-value-wrap');
    const valueInput = document.getElementById('entry-value');
    const valueLabel = document.getElementById('entry-value-label');

    function updateValueVisibility() {
        const mode = modeSelect.value;
        const show = mode !== 'active';
        valueWrap.style.display = show ? 'block' : 'none';
        valueWrap.setAttribute('aria-hidden', show ? 'false' : 'true');
        valueLabel.textContent = mode === 'title' ? 'Title' : 'Code';
        valueInput.placeholder = mode === 'title' ? 'Enter title' : 'Enter code';
    }

    modeSelect.addEventListener('change', updateValueVisibility);
    updateValueVisibility();

    // Suppress Enter submitting forms unexpectedly in modals
    [modal, document.getElementById('participant-modal')].forEach(m => {
        if (!m) return;
        m.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    const savedId = sessionStorage.getItem('selectedPollId');
    if (savedId) {
        if (modal) modal.style.display = 'none';
        showParticipantModal(parseInt(savedId, 10));
        return;
    }
    // Auto-join by URL slug
    const pathSlug = currentPathSlug();
    if (pathSlug) {
        (async () => {
            try {
                // Try all types in order: trivia, survey, poll
                const types = ['trivia','survey','poll'];
                for (const t of types) {
                    try {
                        const res = await fetchJSON(`/poll/by-slug?slug=${encodeURIComponent(pathSlug)}&type=${encodeURIComponent(t)}`);
                        if (res && res.id) {
                            sessionStorage.setItem('selectedPollId', String(res.id));
                            if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
                            showParticipantModal(res.id);
                            return;
                        }
                    } catch (_) { /* continue */ }
                }
                container.innerHTML = '<p>No active session found for this link.</p>';
            } catch (err) {
                try {
                    const st = await getStatusBySlug(pathSlug);
                    if (st && st.exists && (!st.is_active || st.archived)) {
                        renderClosedMessage(container, st);
                    } else {
                        container.innerHTML = '<p>No active session found for this link.</p>';
                    }
                } catch (_) {
                    container.innerHTML = '<p>No active session found for this link.</p>';
                }
            }
        })();
        return;
    }

    if (modal) modal.style.display = 'block';

    form.onsubmit = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const type = typeSelect.value;
        const mode = modeSelect.value;
        const value = (valueInput.value || '').trim();
        if (mode !== 'active' && !value) {
            alert('Please provide a value for the selected join method.');
            return false;
        }
        try {
            const pollId = await findPollIdByEntry(type, mode, value);
            // Persist selection for this tab/session
            sessionStorage.setItem('selectedPollId', String(pollId));
            // Remove the entry modal immediately
            if (modal && modal.parentNode) modal.parentNode.removeChild(modal);
            showParticipantModal(pollId);
            return false;
        } catch (err) {
            console.error(err);
            // Friendlier messaging when no active session
            try {
                const modeIsTitle = mode === 'title';
                const status = modeIsTitle ? await getStatusByTitle(value) : await getStatusBySlug(value);
                if (status && status.exists && (!status.is_active || status.archived)) {
                    renderClosedMessage(container, status);
                } else {
                    container.innerHTML = '<p>No active session found for the selected type. Please check the title/code, or try again when the session is active.</p>';
                }
            } catch (_) {
                container.innerHTML = '<p>No active session found for the selected type. Please check the title/code, or try again when the session is active.</p>';
            }
            alert('No active session found.');
            return false;
        }
    };

    // Online/offline toasts and auto-flush
    window.addEventListener('online', async () => {
        showToast('Back online. Syncing any queued votes...', 'success');
        const sent = await flushQueue();
        if (sent > 0) showToast(`Sent ${sent} queued vote(s).`, 'success');
    });
    window.addEventListener('offline', () => showToast('Offline. Submissions will be queued.', 'warn'));

    // Listen for SW background sync messages
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('message', async (event) => {
            const { type } = event.data || {};
            if (type === 'flushVotes') {
                const sent = await flushQueue();
                if (sent > 0) showToast(`Sent ${sent} queued vote(s).`, 'success');
            }
        });
    }
});