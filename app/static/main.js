// Helper to fetch JSON with error handling
async function fetchJSON(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const err = await resp.text();
        throw new Error(`Error ${resp.status}: ${err}`);
    }
    return await resp.json();
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
        timerEl.textContent = `Time left: ${remaining}s`;
        pollTimer = setInterval(() => {
            remaining--;
            timerEl.textContent = `Time left: ${remaining}s`;
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
            sessionStorage.removeItem('selectedPollId');
            container.innerHTML = '<p>Thank you for voting!</p>';
        } catch (err) {
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
        valueWrap.style.display = (mode === 'active') ? 'none' : 'block';
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
                container.innerHTML = '<p>No active session found for this link.</p>';
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
            container.innerHTML = '<p>No active session found for the selected type. Please check the title/code, or try again when the session is active.</p>';
            alert('No active session found.');
            return false;
        }
    };
});