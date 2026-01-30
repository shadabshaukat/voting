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
    const modal = document.getElementById('participant-modal');
    modal.style.display = 'block';
    const form = document.getElementById('participant-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        const name = form.elements['name'].value.trim();
        const company = form.elements['company'].value.trim();
        if (!name) {
            alert('Name is required');
            return;
        }
        modal.style.display = 'none';
        await startPoll(pollId, { name, company });
    };
}

// ---------- POLL LOGIC ----------
let pollTimer = null;

async function startPoll(pollId, participant) {
    const pollData = await fetchJSON(`/poll/${pollId}`);
    const container = document.getElementById('poll-container');
    container.innerHTML = `<h2>${pollData.title}</h2><p>${pollData.description || ''}</p>`;

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

document.addEventListener('DOMContentLoaded', () => {
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

    if (modal) modal.style.display = 'block';

    form.onsubmit = async (e) => {
        e.preventDefault();
        const type = typeSelect.value;
        const mode = modeSelect.value;
        const value = (valueInput.value || '').trim();
        if (mode !== 'active' && !value) {
            alert('Please provide a value for the selected join method.');
            return;
        }
        try {
            const pollId = await findPollIdByEntry(type, mode, value);
            modal.style.display = 'none';
            showParticipantModal(pollId);
        } catch (err) {
            console.error(err);
            alert('Unable to find an active item: ' + err.message);
            container.innerHTML = '<p>No active items found.</p>';
        }
    };
});