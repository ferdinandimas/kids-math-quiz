let currentQid = null;
let answerStr = "";
let locked = false;
let autoTimer = null;
let popupTimer = null;

const quizDashboard = document.querySelector("[data-reward-per-correct]");
const rewardPerCorrect = quizDashboard.dataset.rewardPerCorrect;
const dailyLimit = Number(quizDashboard.dataset.dailyLimit);

function levelFromAccuracy(accuracy, answered) {
    if ((answered ?? 0) < 50) return "Pemula";
    if (accuracy >= 80) return "Mahir";
    if (accuracy >= 60) return "Menengah";
    return "Pemula";
}

function setMsg(text) {
    document.getElementById("msg").textContent = text || "";
}

function renderAnswer() {
    document.getElementById("answerbox").textContent = answerStr.length ? answerStr : "-";
}

function tap(digit) {
    if (locked || answerStr.length >= 6) return;

    answerStr += digit;
    renderAnswer();

    if (autoTimer) clearTimeout(autoTimer);
    autoTimer = setTimeout(() => {
        if (answerStr.length) nextQ();
    }, 600);
}

async function loadSessionStats() {
    const response = await fetch("/api/stats");
    const data = await response.json();

    document.getElementById("childName").textContent = data.child || "";
    document.getElementById("answered").textContent = data.answered_count ?? 0;
    document.getElementById("correct").textContent = data.correct_count ?? 0;
    document.getElementById("earned").textContent = data.earned ?? 0;

    const answered = Number(data.answered_count ?? 0);
    const currentQuestion = Math.min(answered + 1, dailyLimit);
    document.getElementById("questionProgress").textContent = `Soal ${currentQuestion} dari ${dailyLimit}`;
    document.getElementById("progressFill").style.width = `${Math.max(4, (currentQuestion / dailyLimit) * 100)}%`;

    if (data.recap7?.children && data.child) {
        const recap = data.recap7.children[data.child];
        document.getElementById("level").textContent = levelFromAccuracy(
            recap?.totals?.accuracy_pct ?? 0,
            recap?.totals?.answered_count ?? 0,
        );
    }
}

async function loadQuestion() {
    setMsg("");
    answerStr = "";
    renderAnswer();

    const response = await fetch("/api/question");
    const data = await response.json();

    if (!data.ok) {
        document.getElementById("prompt").textContent = data.message || "Tidak bisa ambil soal.";
        locked = true;
        return;
    }

    currentQid = data.qid;
    document.getElementById("prompt").textContent = data.prompt;
    locked = false;
    await loadSessionStats();
}

async function nextQ() {
    if (autoTimer) clearTimeout(autoTimer);
    autoTimer = null;

    if (locked || !currentQid) return;
    locked = true;

    const response = await fetch("/api/answer", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({qid: currentQid, answer: answerStr}),
    });
    const data = await response.json();

    if (!data.ok) {
        setMsg(data.message || "Ada masalah.");
        locked = false;
        return;
    }

    showPopup({correct: data.correct, correctAnswer: data.correct_answer});

    await loadSessionStats();
}

async function resetAccount() {
    await fetch("/api/logout", {method: "POST"});
    window.location.href = "/home";
}

function showPopup({correct, correctAnswer}) {
    const popup = document.getElementById("popup");
    const card = document.getElementById("popupCard");
    const background = document.getElementById("popupBackground");
    const icon = document.getElementById("popupIcon");
    const title = document.getElementById("popupTitle");
    const text = document.getElementById("popupText");
    const reward = document.getElementById("popupReward");
    const rewardText = document.getElementById("popupRewardText");
    const subtext = document.getElementById("popupSubtext");

    if (popupTimer) clearTimeout(popupTimer);
    card.classList.toggle("is-wrong", !correct);
    card.classList.toggle("is-correct", correct);

    if (correct) {
        background.src = "/static/images/popup-correct-background.png";
        icon.src = "/static/images/popup-correct-icon.png";
        title.textContent = "Benar!";
        text.hidden = true;
        reward.hidden = false;
        rewardText.textContent = `+ Rp ${rewardPerCorrect}`;
        subtext.textContent = "Hebat, lanjutkan ke soal berikutnya ya!";
    } else {
        background.src = "/static/images/popup-wrong-background.png";
        icon.src = "/static/images/popup-wrong-icon.png";
        title.textContent = "Yah kamu salah";
        text.hidden = false;
        reward.hidden = true;
        text.replaceChildren("Jawaban yang benar: ");
        const answerValue = document.createElement("b");
        answerValue.textContent = correctAnswer;
        text.append(answerValue);
        subtext.textContent = "Coba lagi di soal berikutnya ya!";
    }

    popup.style.display = "flex";
    popupTimer = setTimeout(continueAfterPopup, 3000);
}

function hidePopup() {
    if (popupTimer) clearTimeout(popupTimer);
    popupTimer = null;
    document.getElementById("popup").style.display = "none";
}

function continueAfterPopup() {
    if (document.getElementById("popup").style.display === "none") return;
    hidePopup();
    locked = false;
    void loadQuestion();
}

document.getElementById("popup").addEventListener("click", continueAfterPopup);

document.addEventListener("gesturestart", (event) => event.preventDefault());

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js");
}

(async function init() {
    await loadSessionStats();
    await loadQuestion();
}());
