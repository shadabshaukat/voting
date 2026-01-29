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

    pollData.questions.forEach((q) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'question';
        qDiv.innerHTML = `<p><strong>${q.text}</strong></p>`;
        q.choices.forEach((c) => {
            const label = document.createElement('label');
            label.innerHTML = `
                <input type="radio" name="q_${q.id}" value="${c.id}" required>
                ${c.text}
            `;
            qDiv.appendChild(label);
            qDiv.appendChild(document.createElement('br'));
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
            const choiceId = form[`q_${q.id}`].value;
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

// ---------- INITIAL LOAD ----------
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const activePolls = await fetchJSON('/poll/active');
        if (activePolls.length === 0) {
            document.getElementById('poll-container').innerHTML = '<p>No active polls at the moment.</p>';
            return;
        }
        // For simplicity, take the first active poll
        const pollId = activePolls[0].id;
        showParticipantModal(pollId);
    } catch (err) {
        console.error(err);
        document.getElementById('poll-container').innerHTML = '<p>Error loading poll.</p>';
    }
});