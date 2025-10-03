(function () {
    const config = window.AIHelperConfig || {};
    const buttonSelector = config.buttonSelector || '.ai-suggest-button';
    const suggestionSelector = config.suggestionSelector || '.ai-suggestion';

    function escapeSelector(id) {
        if (window.CSS && typeof window.CSS.escape === 'function') {
            return '#' + window.CSS.escape(id);
        }
        return '#' + id.replace(/([\0-\x1F\x7F\-\[\]{}()*+?.,\\^$|#\s])/g, '\\$1');
    }

    function getFieldValue(form, name) {
        if (!form) return '';
        const field = form.querySelector(`[name="${name}"]`);
        return field ? field.value : '';
    }

    async function handleClick(event) {
        const button = event.currentTarget;
        const helperWrapper = button.closest(config.helperWrapperSelector || '.ai-helper');
        const suggestionBox = helperWrapper ? helperWrapper.querySelector(suggestionSelector) : null;
        const targetId = button.getAttribute('data-target');
        const form = button.closest('form');
        const textarea = targetId ? (form ? form.querySelector(escapeSelector(targetId)) : document.querySelector(escapeSelector(targetId))) : null;

        if (!targetId || !textarea || !suggestionBox) {
            return;
        }

        const payload = {
            target: targetId,
            subject: getFieldValue(form, 'subject').trim(),
            product: getFieldValue(form, 'product').trim(),
            issue_description: textarea.value.trim(),
            description: getFieldValue(form, 'description').trim(),
        };

        suggestionBox.classList.remove('error');
        suggestionBox.innerHTML = `<span class="spinner" role="status" aria-hidden="true"></span> <span>Richiesta in corso…</span>`;
        button.disabled = true;

        try {
            const response = await fetch('/ai/suggest', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.suggestion) {
                const message = data.error || data.message || 'Impossibile ottenere un suggerimento in questo momento.';
                throw new Error(message);
            }

            const suggestion = data.suggestion.trim();
            if (suggestion) {
                const currentValue = textarea.value;
                textarea.value = currentValue ? `${currentValue}\n\n${suggestion}` : suggestion;
                textarea.focus();
                textarea.setSelectionRange(textarea.value.length, textarea.value.length);
            }

            suggestionBox.textContent = suggestion || 'Nessun suggerimento disponibile.';
        } catch (error) {
            suggestionBox.classList.add('error');
            suggestionBox.textContent = error.message || 'Si è verificato un errore inatteso.';
        } finally {
            button.disabled = false;
        }
    }

    function init() {
        const buttons = document.querySelectorAll(buttonSelector);
        buttons.forEach((button) => {
            button.addEventListener('click', handleClick);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
