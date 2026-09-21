// ---------- UI strings (kept out of the .po catalog since these are plain JS,
// not templates — keyed off <html lang>, which Django sets from LANGUAGE_CODE) ----------
var MB_T = (function () {
    var strings = {
        ar: {
            installTitle: 'ثبّت التطبيق',
            installDescIOS: 'اضغط على زر المشاركة ثم اختر "إضافة إلى الشاشة الرئيسية"',
            installDescDesktop: 'ثبّت التطبيق على جهازك للوصول السريع',
            installBtn: 'ثبّت',
            installDismiss: 'رفض',
            closeAria: 'إغلاق',
            greetingMorning: 'صباح الخير',
            greetingAfternoon: 'مساء الخير',
            greetingNight: 'ليلة سعيدة',
            greetingWelcomeBack: 'مرحبًا بعودتك.',
            showPassword: 'إظهار كلمة المرور',
            hidePassword: 'إخفاء كلمة المرور',
            pwLevels: ['ضعيفة جدًا', 'ضعيفة', 'متوسطة', 'قوية'],
            pwMatch: 'كلمتا المرور متطابقتان',
            pwNoMatch: 'كلمتا المرور غير متطابقتين',
            aiReading: 'Claude يقرأ المستند…',
            aiFilled: 'تمت تعبئة {n} من الحقول تلقائيًا — راجعها قبل الحفظ.',
            aiKept: 'قرأنا المستند، لكن الحقول التي اقترحناها مملوءة بالفعل فلم نغيّرها.',
            aiNothing: 'لم نستطع قراءة بيانات واضحة من الملف. املأ الحقول يدويًا.',
            aiUnsupported: 'هذا النوع أو الحجم من الملفات غير مدعوم للقراءة التلقائية.',
            aiRateLimited: 'وصلت إلى حد القراءة التلقائية لهذه الساعة. املأ الحقول يدويًا.',
            aiFailed: 'تعذّرت القراءة التلقائية الآن. املأ الحقول يدويًا.',
        },
        en: {
            installTitle: 'Install the app',
            installDescIOS: 'Tap the Share button, then choose "Add to Home Screen"',
            installDescDesktop: 'Install the app on your device for quick access',
            installBtn: 'Install',
            installDismiss: 'Dismiss',
            closeAria: 'Close',
            greetingMorning: 'Good morning',
            greetingAfternoon: 'Good afternoon',
            greetingNight: 'Good night',
            greetingWelcomeBack: 'Welcome back.',
            showPassword: 'Show password',
            hidePassword: 'Hide password',
            pwLevels: ['Very weak', 'Weak', 'Medium', 'Strong'],
            pwMatch: 'Passwords match',
            pwNoMatch: 'Passwords do not match',
            aiReading: 'Claude is reading the document…',
            aiFilled: '{n} field(s) filled automatically — please review before saving.',
            aiKept: 'We read the document, but the fields we could suggest were already filled, so nothing was changed.',
            aiNothing: 'We could not read clear details from the file. Please fill the fields in manually.',
            aiUnsupported: 'This file type or size is not supported for automatic reading.',
            aiRateLimited: 'You have reached the automatic-reading limit for this hour. Please fill the fields in manually.',
            aiFailed: 'Automatic reading is unavailable right now. Please fill the fields in manually.',
        },
    };
    var lang = (document.documentElement.getAttribute('lang') || 'ar').slice(0, 2);
    return strings[lang] || strings.ar;
})();

// ---------- Global page loader (reference-counted, shown on navigation) ----------
var MBSpinner = (function () {
    var _el = null;
    var _count = 0;
    var _safety = null;

    function _getEl() { return _el || (_el = document.getElementById('mbPageLoader')); }

    function _doHide() {
        var s = _getEl();
        if (s) s.classList.remove('active');
    }

    function show() {
        _count++;
        var s = _getEl();
        if (s) s.classList.add('active');
        clearTimeout(_safety);
        _safety = setTimeout(forceHide, 15000);
    }

    function hide() {
        _count = Math.max(0, _count - 1);
        if (_count === 0) { clearTimeout(_safety); _doHide(); }
    }

    function forceHide() {
        clearTimeout(_safety);
        _count = 0;
        _doHide();
    }

    return { show: show, hide: hide, forceHide: forceHide };
})();

// pageshow fires on both normal load AND bfcache restore (back/forward) —
// needed so the loader doesn't stay stuck active after navigating back.
window.addEventListener('pageshow', function () { MBSpinner.forceHide(); });
window.addEventListener('load', function () { MBSpinner.forceHide(); });

document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href]');
    if (!link) return;
    var href = link.getAttribute('href') || '';
    if (!href || href === '#' || /^(javascript:|mailto:|tel:|#)/i.test(href)) return;
    if (link.target === '_blank') return;
    if (link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-dismiss')) return;
    if (link.hasAttribute('download') || link.hasAttribute('data-no-spinner')) return;
    // File-download URLs (archive export, etc.) trigger a browser download, not a
    // page navigation — no load/pageshow event ever fires to clear the spinner.
    if (/\/(export|download|archive)[_\/]|[?&](export|download)=/i.test(href)) return;
    MBSpinner.show();
}, true);

document.addEventListener('submit', function (e) {
    if (!e.defaultPrevented) MBSpinner.show();
});

(function () {
    var trigger = document.getElementById('mbNotifTrigger');
    if (!trigger) return;

    var menu = document.getElementById('mbNotifMenu');
    var dropdown = document.getElementById('mbNotifDropdown');
    var badge = document.getElementById('mbNotifBadge');

    function refreshCount() {
        fetch('/notifications/unread-count/')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.count > 0) {
                    badge.textContent = data.count > 9 ? '9+' : data.count;
                    badge.classList.remove('d-none');
                    badge.classList.add('mb-notif-badge--pulse');
                } else {
                    badge.classList.add('d-none');
                    badge.classList.remove('mb-notif-badge--pulse');
                }
            })
            .catch(function () { /* silent — next poll retries */ });
    }

    function loadDropdown() {
        dropdown.innerHTML = '<div class="text-center text-muted py-4 small">...</div>';
        fetch('/notifications/dropdown/')
            .then(function (r) { return r.text(); })
            .then(function (html) {
                dropdown.innerHTML = html;
                refreshCount();
            });
    }

    menu.addEventListener('show.bs.dropdown', loadDropdown);
    refreshCount();
    setInterval(refreshCount, 45000);
})();

// ---------- Toasts ----------
(function () {
    var stack = document.getElementById('mbToastStack');
    if (!stack) return;

    function dismiss(toast) {
        toast.classList.add('mb-toast--leaving');
        setTimeout(function () { toast.remove(); }, 200);
    }

    Array.prototype.forEach.call(stack.children, function (toast, i) {
        setTimeout(function () { toast.classList.add('mb-toast--visible'); }, 20 + i * 80);
        var closeBtn = toast.querySelector('.mb-toast__close');
        if (closeBtn) closeBtn.addEventListener('click', function () { dismiss(toast); });
        setTimeout(function () { dismiss(toast); }, 5000 + i * 400);
    });
})();

// ---------- Scroll reveal ----------
(function () {
    var targets = document.querySelectorAll('.mb-reveal');
    if (!targets.length) return;

    if (!('IntersectionObserver' in window)) {
        targets.forEach(function (el) { el.classList.add('mb-reveal--visible'); });
        return;
    }

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('mb-reveal--visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: .12, rootMargin: '0px 0px -30px 0px' });

    targets.forEach(function (el) { observer.observe(el); });
})();

// ---------- Count-up numbers ----------
(function () {
    var counters = document.querySelectorAll('.mb-count');
    if (!counters.length) return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    counters.forEach(function (el) {
        var target = parseInt(el.getAttribute('data-count'), 10) || 0;
        if (reduceMotion || target === 0) { el.textContent = target; return; }

        var duration = 800;
        var start = null;
        function step(ts) {
            if (start === null) start = ts;
            var progress = Math.min((ts - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(eased * target);
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    });
})();

// ---------- Submit buttons: loading state ----------
(function () {
    document.addEventListener('submit', function (e) {
        var form = e.target;
        var btn = form.querySelector('button[type="submit"]');
        if (!btn || btn.disabled) return;
        // Disabling the button that triggered submission can strip its own
        // name/value from the submitted form data (or cancel the submit
        // outright) in some browsers — e.g. the language-toggle button,
        // whose value:"ar"/"en" IS the form's payload. A hidden input copy
        // keeps that data flowing regardless of the button's disabled state.
        if (btn.name) {
            var hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = btn.name;
            hidden.value = btn.value;
            form.appendChild(hidden);
        }
        btn.disabled = true;
        btn.dataset.originalHtml = btn.innerHTML;
        btn.innerHTML = '<span class="mb-spinner-inline"></span> ' + btn.textContent.trim();
    });
})();

// ---------- Theme toggle ----------
(function () {
    var btn = document.getElementById('mbThemeToggle');
    if (!btn) return;

    var iconLight = document.getElementById('mbThemeIconLight');
    var iconDark = document.getElementById('mbThemeIconDark');
    var root = document.documentElement;

    function syncIcon() {
        var isLight = root.getAttribute('data-bs-theme') === 'light';
        iconLight.classList.toggle('d-none', isLight);
        iconDark.classList.toggle('d-none', !isLight);
    }

    syncIcon();

    btn.addEventListener('click', function () {
        var next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-bs-theme', next);
        try { localStorage.setItem('mbTheme', next); } catch (e) {}
        syncIcon();
    });
})();

// ---------- Confirm modal ----------
function mbConfirm(options) {
    var modalEl = document.getElementById('mbConfirmModal');
    if (!modalEl) { if (options.onConfirm) options.onConfirm(); return; }

    modalEl.querySelector('.mb-confirm-title').textContent = options.title || '';
    modalEl.querySelector('.mb-confirm-message').textContent = options.message || '';
    var confirmBtn = modalEl.querySelector('.mb-confirm-btn');
    confirmBtn.textContent = options.confirmLabel || confirmBtn.textContent;

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    var newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
    newBtn.addEventListener('click', function () {
        modal.hide();
        if (options.onConfirm) options.onConfirm();
    });
    modal.show();
}

// ---------- File dropzone (click-to-pick via <label>, plus drag & drop) ----------
function mbInitFileDrop(dropId) {
    var drop = document.getElementById(dropId);
    if (!drop) return;
    var input = drop.querySelector('input[type="file"]');
    var text = document.getElementById('mbFileDropText');
    var icon = document.getElementById('mbFileDropIcon');
    if (!input || !text) return;

    function showFile(name) {
        text.textContent = name;
        drop.classList.add('mb-file-drop--filled');
        if (icon) { icon.classList.remove('bi-cloud-arrow-up'); icon.classList.add('bi-file-earmark-check'); }
    }

    input.addEventListener('change', function () {
        if (input.files && input.files[0]) showFile(input.files[0].name);
    });

    ['dragenter', 'dragover'].forEach(function (evt) {
        drop.addEventListener(evt, function (e) { e.preventDefault(); drop.classList.add('mb-file-drop--dragging'); });
    });
    ['dragleave', 'drop'].forEach(function (evt) {
        drop.addEventListener(evt, function (e) { e.preventDefault(); drop.classList.remove('mb-file-drop--dragging'); });
    });
    drop.addEventListener('drop', function (e) {
        var files = e.dataTransfer && e.dataTransfer.files;
        if (files && files[0]) {
            input.files = files;
            // Fires the same 'change' listener as a normal pick (which calls showFile),
            // and lets other features (e.g. mbInitAiExtract) react to dropped files too.
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
}

// ---------- Upload form: pre-fill fields by having Claude read the chosen file ----------
// The form opts in with data-extract-url (only rendered when the server has the
// feature enabled). Only EMPTY fields are filled, and filled ones are highlighted
// until the user edits them, so nothing is silently overwritten or silently trusted.
function mbInitAiExtract(formId) {
    var form = document.getElementById(formId);
    if (!form || !form.dataset.extractUrl) return;
    var input = form.querySelector('input[type="file"]');
    var status = document.getElementById('mbAiStatus');
    var tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!input || !status || !tokenInput) return;

    var fieldIds = { title: 'id_title', category_id: 'id_category', issue_date: 'id_issue_date', expiry_date: 'id_expiry_date' };
    var latest = 0;

    function setStatus(kind, text) {
        var icons = { busy: 'bi-hourglass-split', ok: 'bi-stars', warn: 'bi-info-circle' };
        status.hidden = false;
        status.className = 'mb-ai-status mb-ai-status--' + kind;
        status.innerHTML = '<i class="bi ' + icons[kind] + '"></i> ';
        status.appendChild(document.createTextNode(text));
    }

    function fill(result) {
        var filled = 0, suggested = 0;
        Object.keys(fieldIds).forEach(function (key) {
            var value = result[key];
            var el = document.getElementById(fieldIds[key]);
            if (value === null || value === undefined || !el) return;
            suggested++;
            if (el.value) return;
            el.value = value;
            el.classList.add('mb-ai-filled');
            el.addEventListener('input', function () { el.classList.remove('mb-ai-filled'); }, { once: true });
            el.addEventListener('change', function () { el.classList.remove('mb-ai-filled'); }, { once: true });
            filled++;
        });
        return { filled: filled, suggested: suggested };
    }

    input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file) return;
        var mine = ++latest;
        setStatus('busy', MB_T.aiReading);

        var data = new FormData();
        data.append('file', file);
        fetch(form.dataset.extractUrl, {
            method: 'POST', body: data, credentials: 'same-origin',
            headers: { 'X-CSRFToken': tokenInput.value },
        }).then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (body) { return { status: res.status, body: body }; });
        }).then(function (res) {
            if (mine !== latest) return; // a newer file was chosen meanwhile
            if (res.status === 200) {
                var out = fill(res.body);
                if (out.filled) setStatus('ok', MB_T.aiFilled.replace('{n}', out.filled));
                else setStatus('warn', out.suggested ? MB_T.aiKept : MB_T.aiNothing);
            } else if (res.status === 422) setStatus('warn', MB_T.aiUnsupported);
            else if (res.status === 429) setStatus('warn', MB_T.aiRateLimited);
            else setStatus('warn', MB_T.aiFailed);
        }).catch(function () {
            if (mine === latest) setStatus('warn', MB_T.aiFailed);
        });
    });
}

// ---------- Navbar: shrink slightly on scroll ----------
(function () {
    var nav = document.querySelector('.mb-navbar');
    if (!nav) return;
    function sync() { nav.classList.toggle('mb-navbar--scrolled', window.scrollY > 12); }
    sync();
    window.addEventListener('scroll', sync, { passive: true });
})();

// ---------- Navbar dropdowns: pin to the viewport on narrow screens ----------
// data-bs-display="static" stops Popper from positioning these menus, but its
// own CSS "static position" fallback can still miscompute against a narrow
// icon-button anchor and push the menu past the screen edge. Below the
// lg breakpoint, position it explicitly from the navbar's real, live
// bounding box instead of guessing a fixed offset.
(function () {
    var MOBILE_BREAKPOINT = 992;

    document.querySelectorAll('.mb-navbar-dropdown').forEach(function (menu) {
        var toggle = menu.previousElementSibling;
        if (!toggle) return;

        toggle.addEventListener('show.bs.dropdown', function () {
            if (window.innerWidth >= MOBILE_BREAKPOINT) {
                menu.style.cssText = '';
                return;
            }
            var navRect = document.querySelector('.mb-navbar').getBoundingClientRect();
            menu.style.position = 'fixed';
            menu.style.top = (navRect.bottom + 8) + 'px';
            menu.style.insetInlineStart = '12px';
            menu.style.insetInlineEnd = '12px';
            menu.style.left = '12px';
            menu.style.right = '12px';
            menu.style.width = 'auto';
            menu.style.maxWidth = 'none';
            menu.style.margin = '0';
        });

        toggle.addEventListener('hidden.bs.dropdown', function () {
            menu.style.cssText = '';
        });
    });

    window.addEventListener('resize', function () {
        document.querySelectorAll('.mb-navbar-dropdown.show').forEach(function (menu) {
            var toggle = menu.previousElementSibling;
            if (toggle) toggle.dispatchEvent(new Event('show.bs.dropdown'));
        });
    });
})();

/* تثبيت التطبيق (PWA Install Prompt) */
(function setupPWAInstallPrompt() {
    var installPrompt = null;
    var ua = navigator.userAgent.toLowerCase();
    var isiOS = /iphone|ipad|ipod/.test(ua);
    var promptShownKey = 'mbPwaPromptShown';
    var iOSPromptKey = 'mbPwaIosPromptShown';

    function isAppAlreadyInstalled() {
        return window.navigator.standalone === true ||
            window.matchMedia('(display-mode: standalone)').matches;
    }

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        installPrompt = e;
        showInstallBanner('desktop');
    });

    if (isiOS && !sessionStorage.getItem(iOSPromptKey) && !isAppAlreadyInstalled()) {
        setTimeout(function () {
            showInstallBanner('ios');
            sessionStorage.setItem(iOSPromptKey, 'true');
        }, 3000);
    }

    function showInstallBanner(type) {
        if (sessionStorage.getItem(promptShownKey + '_' + type)) return;

        var banner = document.createElement('div');
        banner.className = 'mb-pwa-banner mb-pwa-banner--' + type;
        banner.setAttribute('role', 'alert');
        banner.innerHTML = type === 'ios' ?
            '<div class="mb-pwa-banner__content">' +
                '<div class="mb-pwa-banner__icon"><i class="bi bi-download"></i></div>' +
                '<div class="mb-pwa-banner__text">' +
                    '<div class="mb-pwa-banner__title">' + MB_T.installTitle + '</div>' +
                    '<div class="mb-pwa-banner__description">' + MB_T.installDescIOS + '</div>' +
                '</div>' +
                '<button type="button" class="mb-pwa-banner__close" aria-label="' + MB_T.closeAria + '"><i class="bi bi-x-lg"></i></button>' +
            '</div>' :
            '<div class="mb-pwa-banner__content">' +
                '<div class="mb-pwa-banner__icon"><i class="bi bi-download"></i></div>' +
                '<div class="mb-pwa-banner__text">' +
                    '<div class="mb-pwa-banner__title">' + MB_T.installTitle + '</div>' +
                    '<div class="mb-pwa-banner__description">' + MB_T.installDescDesktop + '</div>' +
                '</div>' +
                '<div class="mb-pwa-banner__actions">' +
                    '<button type="button" class="mb-pwa-banner__btn mb-pwa-banner__btn--primary" data-action="install">' + MB_T.installBtn + '</button>' +
                    '<button type="button" class="mb-pwa-banner__btn mb-pwa-banner__btn--secondary" data-action="dismiss">' + MB_T.installDismiss + '</button>' +
                '</div>' +
            '</div>';

        document.body.insertBefore(banner, document.body.firstChild);
        sessionStorage.setItem(promptShownKey + '_' + type, 'true');

        function dismiss() {
            banner.classList.add('mb-pwa-banner--hidden');
            setTimeout(function () { banner.remove(); }, 300);
        }

        var closeBtn = banner.querySelector('.mb-pwa-banner__close');
        if (closeBtn) closeBtn.addEventListener('click', dismiss);

        var installBtn = banner.querySelector('[data-action="install"]');
        var dismissBtn = banner.querySelector('[data-action="dismiss"]');

        if (installBtn) {
            installBtn.addEventListener('click', function () {
                if (installPrompt) {
                    installPrompt.prompt();
                    installPrompt.userChoice.then(function (choice) {
                        if (choice.outcome === 'accepted') dismiss();
                    });
                }
            });
        }
        if (dismissBtn) dismissBtn.addEventListener('click', dismiss);

        setTimeout(function () {
            if (document.body.contains(banner)) dismiss();
        }, 10000);
    }

    window.addEventListener('appinstalled', function () {
        sessionStorage.removeItem(promptShownKey + '_desktop');
    });
})();

// ---------- Auth pages: password toggle, strength meter, live match ----------
(function () {
    var card = document.querySelector('.mb-auth-card');
    if (!card) return;

    // Time-of-day greeting on the login page
    var greeting = document.getElementById('mbGreeting');
    if (greeting) {
        var hour = new Date().getHours();
        var prefix = hour < 5 ? MB_T.greetingNight : hour < 12 ? MB_T.greetingMorning : hour < 21 ? MB_T.greetingAfternoon : MB_T.greetingNight;
        greeting.textContent = prefix + '. ' + MB_T.greetingWelcomeBack;
    }

    // Show/hide password
    card.querySelectorAll('input[type="password"]').forEach(function (input) {
        var wrap = input.closest('.mb-field__control');
        if (!wrap) return;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mb-pw-toggle';
        btn.setAttribute('aria-label', MB_T.showPassword);
        btn.innerHTML = '<i class="bi bi-eye"></i>';
        wrap.appendChild(btn);
        btn.addEventListener('click', function () {
            var showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';
            btn.innerHTML = showing ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
            btn.setAttribute('aria-label', showing ? MB_T.showPassword : MB_T.hidePassword);
        });
    });

    // Strength meter on the primary new-password field
    var primaryPw = card.querySelector('#id_password1, #id_new_password1');
    if (primaryPw) {
        var meter = document.createElement('div');
        meter.className = 'mb-pw-meter';
        meter.innerHTML =
            '<div class="mb-pw-meter__track">' +
                '<div class="mb-pw-meter__seg"></div><div class="mb-pw-meter__seg"></div>' +
                '<div class="mb-pw-meter__seg"></div><div class="mb-pw-meter__seg"></div>' +
            '</div>' +
            '<div class="mb-pw-meter__label"></div>';
        primaryPw.closest('.mb-field').insertAdjacentElement('afterend', meter);

        var segs = meter.querySelectorAll('.mb-pw-meter__seg');
        var label = meter.querySelector('.mb-pw-meter__label');
        var levels = MB_T.pwLevels;
        var icons = ['bi-shield-x', 'bi-shield-exclamation', 'bi-shield-check', 'bi-shield-fill-check'];

        primaryPw.addEventListener('input', function () {
            var val = primaryPw.value;
            segs.forEach(function (s) { s.className = 'mb-pw-meter__seg'; });
            if (!val) { label.className = 'mb-pw-meter__label'; return; }

            var score = 0;
            if (val.length >= 8) score++;
            if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score++;
            if (/[0-9]/.test(val)) score++;
            if (/[^A-Za-z0-9]/.test(val)) score++;
            var level = val.length < 4 ? 0 : Math.max(0, score - 1);
            level = Math.min(level, 3);

            for (var i = 0; i <= level; i++) {
                segs[i].className = 'mb-pw-meter__seg mb-pw-meter__seg--on mb-pw-meter--' + level;
            }
            label.className = 'mb-pw-meter__label mb-pw-meter__label--visible mb-pw-meter__label--' + level;
            label.innerHTML = '<i class="bi ' + icons[level] + '"></i> ' + levels[level];
        });
    }

    // Live match indicator between the two password fields
    var pairs = [['#id_password1', '#id_password2'], ['#id_new_password1', '#id_new_password2']];
    pairs.forEach(function (pair) {
        var first = card.querySelector(pair[0]);
        var second = card.querySelector(pair[1]);
        if (!first || !second) return;

        var indicator = document.createElement('div');
        indicator.className = 'mb-pw-match';
        second.closest('.mb-field').insertAdjacentElement('afterend', indicator);

        function checkMatch() {
            if (!second.value) { indicator.className = 'mb-pw-match'; return; }
            var ok = first.value === second.value;
            indicator.className = 'mb-pw-match mb-pw-match--visible ' + (ok ? 'mb-pw-match--ok' : 'mb-pw-match--no');
            indicator.innerHTML = ok
                ? '<i class="bi bi-check-circle-fill"></i> ' + MB_T.pwMatch
                : '<i class="bi bi-x-circle-fill"></i> ' + MB_T.pwNoMatch;
        }
        second.addEventListener('input', checkMatch);
        first.addEventListener('input', function () { if (second.value) checkMatch(); });
    });

})();
