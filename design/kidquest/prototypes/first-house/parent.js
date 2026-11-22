/*
 * KidQuest first-house prototype — adult gate and adult-gated shell (KQ-005).
 * UI simulation only. The adult session lives in page memory: a reload asks
 * for the PIN again. Real authorization (PBKDF2 PIN hash, HMAC-signed
 * HttpOnly SameSite=Strict short-lived cookie) is KQ-011 scope (PRD §4.4).
 */
(function () {
    'use strict';

    var STORE_KEY = 'kq-proto-first-house-v1';
    var SIM_KEY = 'kq-proto-sim-v1';
    var PROTO_PIN = '2468';
    var NAMES = { althafandra: 'Althafandra', alleia: 'Alleia' };
    var QUEST_LABEL = {
        AVAILABLE: 'Belum dimulai', IN_PROGRESS: 'Sedang dikerjakan', READY_TO_BUILD: 'Siap membangun', COMPLETED: 'Selesai'
    };
    var THEME_LABEL = { perkampungan: 'Kampung Ceria', kingdom: 'Kerajaan Ceria', city: 'Kota Ceria' };
    var ALL_SECTIONS = [
        ['ringkasan', 'Ringkasan'], ['belajar', 'Belajar'], ['ekonomi', 'Ekonomi', true], ['pencairan', 'Pencairan', true], ['pengaturan', 'Pengaturan']
    ];
    // Lead decision C7 (2026-11-21): economy sections are absent, not empty, while the economy is disabled.
    function economyEnabled() {
        try { var raw = window.localStorage.getItem(SIM_KEY); return !!(raw && JSON.parse(raw).economy); } catch (e) { return false; }
    }
    function sections() {
        var on = economyEnabled();
        return ALL_SECTIONS.filter(function (s) { return on || !s[2]; });
    }
    var SCOPES = {
        legacy: { label: 'Riwayat Kuis saja', detail: 'Menghapus riwayat Kuis anak ini. Dunia KidQuest tetap ada.', word: 'HAPUS-KUIS' },
        kidquest: { label: 'Dunia KidQuest saja', detail: 'Menghapus pulau, bangunan, misi, dan percobaan KidQuest anak ini. Riwayat Kuis tetap ada.', word: 'HAPUS-DUNIA' },
        all: { label: 'Semua data anak ini', detail: 'Menghapus riwayat Kuis dan dunia KidQuest anak ini. Anak lain tidak terpengaruh.', word: 'HAPUS-SEMUA' }
    };

    var ui = { authed: false, section: 'ringkasan', gateError: null, gateNote: null, busy: false, reset: null, focus: null };

    function $(s) { return document.querySelector(s); }
    function announce(t) { var l = $('#live'); l.textContent = ''; window.setTimeout(function () { l.textContent = t; }, 40); }
    function worlds() {
        try { var raw = window.localStorage.getItem(STORE_KEY); return raw ? (JSON.parse(raw).worlds || {}) : {}; } catch (e) { return {}; }
    }

    function gate() {
        return '<header class="adult-bar"><strong>KidQuest</strong><span class="adult-mode-flag">Area Orang Tua</span></header>' +
            '<main id="main" class="adult-gate" tabindex="-1">' +
            '<h1 id="gate-title" tabindex="-1" style="font-size:1.5rem">Area Orang Tua</h1>' +
            '<p>Halaman ini untuk orang tua. Masukkan PIN orang tua untuk melanjutkan.</p>' +
            (ui.gateNote ? '<div class="alert alert-info" role="status"><div><p>' + ui.gateNote + '</p></div></div>' : '') +
            '<form id="gate-form" class="card stack" novalidate>' +
            '<div class="field"><label for="pin">PIN orang tua</label>' +
            '<input id="pin" type="password" inputmode="numeric" autocomplete="off" maxlength="8"' + (ui.gateError ? ' aria-invalid="true" aria-describedby="pin-err"' : '') + '>' +
            (ui.gateError ? '<p id="pin-err" class="alert alert-error" role="alert" style="margin:0"><span style="color:var(--s-ink)">' + ui.gateError + '</span></p>' : '') +
            '</div>' +
            '<button class="btn btn-primary" type="submit"' + (ui.busy ? ' disabled' : '') + '>' + (ui.busy ? 'Memeriksa…' : 'Masuk') + '</button>' +
            '</form>' +
            '<a class="btn btn-secondary" href="index.html">Kembali ke Mode Anak</a>' +
            '</main>';
    }

    function childCards() {
        var w = worlds();
        return Object.keys(NAMES).map(function (id) {
            var st = w[id];
            if (!st) {
                return '<article class="card"><h3>' + NAMES[id] + '</h3><p class="muted">Belum membuka KidQuest.</p></article>';
            }
            return '<article class="card"><h3>' + NAMES[id] + '</h3><dl class="kv">' +
                '<dt>Misi Rumah Pertama</dt><dd>' + QUEST_LABEL[st.quest] + '</dd>' +
                '<dt>Rumah dibangun</dt><dd>' + (st.buildings.length ? 'Ya' : 'Belum') + '</dd>' +
                '<dt>Percobaan menjawab</dt><dd>' + st.attempts + '</dd>' +
                '<dt>Petunjuk dipakai</dt><dd>' + st.hints + '</dd>' +
                '<dt>Tema</dt><dd>' + THEME_LABEL[st.theme] + '</dd></dl></article>';
        }).join('');
    }

    function sectionBody() {
        var w = worlds();
        if (ui.section === 'ringkasan') {
            return '<h2 id="sec-title" tabindex="-1">Ringkasan</h2>' +
                '<div class="alert alert-success" role="status"><div><p>Tidak ada keputusan yang menunggu.</p></div></div>' +
                '<div class="data-cards">' + childCards() + '</div>' +
                '<p class="muted">Data contoh dari prototipe di perangkat ini.</p>';
        }
        if (ui.section === 'belajar') {
            return '<h2 id="sec-title" tabindex="-1">Belajar · 7 hari terakhir</h2><div class="data-cards">' +
                Object.keys(NAMES).map(function (id) {
                    var st = w[id];
                    if (!st || st.attempts === 0) {
                        return '<article class="card"><h3>' + NAMES[id] + '</h3><p>Belum ada latihan KidQuest dalam 7 hari terakhir.</p></article>';
                    }
                    var tip = (st.hints > 0 || st.attempts > 1)
                        ? 'Latih menghitung maju dari 6 sampai 10 dengan benda di rumah, misalnya sendok atau balok.'
                        : 'Pengurangan sampai 10 di misi ini sudah lancar.';
                    return '<article class="card"><h3>' + NAMES[id] + '</h3><dl class="kv">' +
                        '<dt>Keterampilan</dt><dd>Pengurangan dasar</dd>' +
                        '<dt>Percobaan</dt><dd>' + st.attempts + '</dd>' +
                        '<dt>Petunjuk</dt><dd>' + st.hints + '</dd>' +
                        '<dt>Misi selesai</dt><dd>' + (st.quest === 'COMPLETED' ? 1 : 0) + '</dd></dl>' +
                        '<p><strong>Saran latihan:</strong> ' + tip + '</p></article>';
                }).join('') + '</div>';
        }
        if (ui.section === 'ekonomi' || ui.section === 'pencairan') {
            // Only reachable when the economy is enabled; the content itself is KQ-016 scope.
            return '<h2 id="sec-title" tabindex="-1">' + (ui.section === 'ekonomi' ? 'Ekonomi' : 'Pencairan') + '</h2>' +
                '<div class="alert alert-info" role="status"><div><p>Prototipe berhenti di sini. Isi bagian ini dirancang di KQ-016 (ekonomi orang tua dan pencairan).</p></div></div>';
        }
        return settings();
    }

    function settings() {
        var r = ui.reset || { child: 'althafandra', scope: null, step: 'choose', typed: '' };
        ui.reset = r;
        var head = '<h2 id="sec-title" tabindex="-1">Pengaturan</h2>';
        if (r.step === 'done') {
            return head + '<div class="alert alert-info" role="status"><div><p><strong>Simulasi selesai.</strong> Tidak ada data yang dihapus di prototipe ini. Di aplikasi asli, penghapusan ' +
                SCOPES[r.scope].label.toLowerCase() + ' untuk ' + NAMES[r.child] + ' dicatat di log audit.</p>' +
                '<button class="btn btn-secondary" data-act="reset-again">Kembali ke Pengaturan</button></div></div>';
        }
        if (r.step === 'review') {
            var s = SCOPES[r.scope];
            var ok = r.typed.trim() === s.word;
            return head + '<section class="card" aria-labelledby="rv-title"><h3 id="rv-title" tabindex="-1">Tinjau penghapusan</h3>' +
                '<dl class="kv"><dt>Anak</dt><dd>' + NAMES[r.child] + '</dd><dt>Yang dihapus</dt><dd>' + s.label + '</dd></dl>' +
                '<p>' + s.detail + ' Tindakan ini tidak bisa dibatalkan.</p>' +
                '<div class="field"><label for="confirm-word">Ketik <strong>' + s.word + '</strong> untuk konfirmasi</label>' +
                '<input id="confirm-word" type="text" autocomplete="off" value="' + r.typed + '"></div>' +
                '<div class="btn-row"><button class="btn btn-danger" data-act="reset-do"' + (ok ? '' : ' disabled') + '>Hapus ' + s.label + '</button>' +
                '<button class="btn btn-secondary" data-act="reset-cancel">Batal</button></div></section>';
        }
        return head + '<section class="card" aria-labelledby="rs-title"><h3 id="rs-title">Hapus data per anak</h3>' +
            '<div class="field"><label for="child-select">Anak</label><select id="child-select">' +
            Object.keys(NAMES).map(function (id) { return '<option value="' + id + '"' + (r.child === id ? ' selected' : '') + '>' + NAMES[id] + '</option>'; }).join('') +
            '</select></div>' +
            '<fieldset class="radio-list" style="border:0;padding:0;margin:0"><legend style="font-weight:800;margin-bottom:6px">Pilih yang akan dihapus</legend>' +
            Object.keys(SCOPES).map(function (k) {
                return '<label><input type="radio" name="scope" value="' + k + '"' + (r.scope === k ? ' checked' : '') + '><span><strong>' + SCOPES[k].label + '</strong><br><span class="help">' + SCOPES[k].detail + '</span></span></label>';
            }).join('') + '</fieldset>' +
            '<button class="btn btn-secondary" data-act="reset-review"' + (r.scope ? '' : ' disabled') + '>Tinjau</button>' +
            (r.scope ? '' : '<p class="help">Pilih salah satu dulu.</p>') + '</section>';
    }

    function shell() {
        return '<header class="adult-bar"><strong>KidQuest</strong>' +
            '<span class="adult-mode-flag">Mode Orang Tua aktif</span>' +
            '<button class="btn btn-secondary" data-act="exit">Keluar dari Mode Orang Tua</button></header>' +
            '<div class="adult-layout">' +
            '<nav class="adult-nav" aria-label="Bagian orang tua">' + sections().map(function (s) {
                return '<button class="btn" data-act="section" data-id="' + s[0] + '"' + (ui.section === s[0] ? ' aria-current="page"' : '') + '>' + s[1] + '</button>';
            }).join('') + '</nav>' +
            '<main id="main" class="stack" tabindex="-1">' +
            '<p class="muted">Sesi orang tua berakhir otomatis setelah beberapa menit. Anak tidak bisa membuka halaman ini tanpa PIN.</p>' +
            sectionBody() + '</main></div>';
    }

    function render() {
        var visible = sections().map(function (s) { return s[0]; });
        if (visible.indexOf(ui.section) < 0) { ui.section = 'ringkasan'; }
        $('#adult-app').innerHTML = ui.authed ? shell() : gate();
        var t = ui.focus ? $(ui.focus) : null;
        ui.focus = null;
        if (t) { t.focus(); }
    }

    document.addEventListener('submit', function (e) {
        if (e.target.id !== 'gate-form') { return; }
        e.preventDefault();
        var pin = $('#pin').value;
        ui.busy = true; render();
        window.setTimeout(function () {
            ui.busy = false;
            if (pin === PROTO_PIN) {
                ui.authed = true; ui.gateError = null; ui.gateNote = null; ui.section = 'ringkasan';
                ui.focus = '#sec-title';
                announce('Mode Orang Tua aktif.');
            } else {
                ui.gateError = 'PIN tidak cocok. Coba lagi.';
                ui.focus = '#pin';
            }
            render();
        }, 400);
    });

    document.addEventListener('click', function (e) {
        var t = e.target.closest('[data-act]');
        if (t && !t.disabled) {
            var a = t.dataset.act;
            if (a === 'section') { ui.section = t.dataset.id; ui.focus = '#sec-title'; render(); }
            if (a === 'exit') { ui.authed = false; window.location.href = 'index.html'; }
            if (a === 'reset-review') { ui.reset.step = 'review'; ui.reset.typed = ''; ui.focus = '#rv-title'; render(); }
            if (a === 'reset-cancel') { ui.reset.step = 'choose'; ui.focus = '#sec-title'; render(); announce('Dibatalkan. Tidak ada yang dihapus.'); }
            if (a === 'reset-do') { ui.reset.step = 'done'; ui.focus = '#sec-title'; render(); }
            if (a === 'reset-again') { ui.reset = null; ui.focus = '#sec-title'; render(); }
        }
        var r = e.target.closest('[data-rev]');
        if (r && r.dataset.rev === 'economy') {
            try {
                var sim = JSON.parse(window.localStorage.getItem(SIM_KEY) || '{}');
                sim.economy = !sim.economy;
                window.localStorage.setItem(SIM_KEY, JSON.stringify(sim));
            } catch (err) { /* storage unavailable */ }
            r.textContent = 'Ekonomi diaktifkan (simulasi): ' + (economyEnabled() ? 'ya' : 'tidak');
            render();
            return;
        }
        if (r && r.dataset.rev === 'expire') {
            ui.authed = false; ui.reset = null;
            ui.gateNote = 'Sesi orang tua berakhir. Masukkan PIN lagi untuk melanjutkan.';
            ui.focus = '#gate-title';
            render();
        }
    });

    document.addEventListener('change', function (e) {
        if (e.target.id === 'child-select') { ui.reset.child = e.target.value; }
        if (e.target.name === 'scope') { ui.reset.scope = e.target.value; ui.focus = 'input[name="scope"][value="' + e.target.value + '"]'; render(); }
    });

    document.addEventListener('input', function (e) {
        if (e.target.id === 'confirm-word') {
            ui.reset.typed = e.target.value;
            var btn = document.querySelector('[data-act="reset-do"]');
            if (btn) { btn.disabled = e.target.value.trim() !== SCOPES[ui.reset.scope].word; }
        }
    });

    ui.focus = '#gate-title';
    render();
}());
