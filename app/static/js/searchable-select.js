/* LBB Searchable Select
 * Shared Bootstrap 5.3 searchable-select built on Bootstrap's own Dropdown.
 * The native <select> stays the single source of truth: choosing an option
 * sets select.value and dispatches a bubbling "change". Escapes overflow
 * clipping (modals, .table-responsive) via Popper strategy:"fixed".
 *
 * Public API on window.LbbSearchableSelect:
 *   init(root)      enhance every matching select inside root
 *   enhance(select) enhance a single select
 *   refresh(select) re-sync label/options from the native select
 *   destroy(select) tear down the enhancement
 */
(function (root, factory) {
  var core = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = core;
  }
  if (root && root.document) {
    root.LbbSearchableSelect = core.createBrowserManager(root);
    root.LbbSearchableSelect.start();
  }
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  var SELECTOR = "select.form-select, select[data-searchable-select]";
  var RENDER_CAP = 100;
  var uidCounter = 0;

  function asArray(value) {
    return Array.prototype.slice.call(value || []);
  }

  function optionText(option) {
    return String(option.textContent || "").replace(/\s+/g, " ").trim();
  }

  function shouldSortSelectOptions(select) {
    if (select.dataset.sortOptions === "none") return false;
    if (select.dataset.sortOptions === "az") return true;

    var fieldName = String(select.name || select.id || "").toLowerCase();
    if (/(month|year|per_page|page_size|status|sort|method|billing_type|period|date)/.test(fieldName)) {
      return false;
    }

    return true;
  }

  function sortSelectOptions(select) {
    if (!shouldSortSelectOptions(select)) return;
    // Only sort flat option lists; leave <optgroup> structures untouched.
    if (select.querySelector("optgroup")) return;

    var selectedValue = select.value;
    var options = asArray(select.options);
    var placeholderOptions = options.filter(function (option) {
      return option.value === "";
    });
    var valueOptions = options.filter(function (option) {
      return option.value !== "";
    });

    valueOptions.sort(function (left, right) {
      return optionText(left).localeCompare(optionText(right), "id", {
        sensitivity: "base",
        numeric: true,
      });
    });

    select.replaceChildren();
    placeholderOptions.concat(valueOptions).forEach(function (option) {
      select.appendChild(option);
    });
    select.value = selectedValue;
  }

  function blankOption(select) {
    return asArray(select.options).filter(function (option) {
      return option.value === "";
    })[0] || null;
  }

  function placeholderText(select) {
    var explicit = select.getAttribute("data-placeholder");
    if (explicit) return explicit;
    var blank = blankOption(select);
    if (blank) {
      var text = optionText(blank);
      if (text) return text;
    }
    return "Pilih\u2026";
  }

  function selectedOption(select) {
    return select.selectedIndex >= 0 ? select.options[select.selectedIndex] : null;
  }

  function createBrowserManager(win) {
    var doc = win.document;
    var bootstrap = win.bootstrap;
    var domObserver = null;
    var pending = null;

    function enhance(select) {
      if (!select || select.tagName !== "SELECT") return;
      if (select.multiple) return;
      if (select.dataset.lbbSearchableReady === "1") return;
      if (!bootstrap || !bootstrap.Dropdown) return;

      var hasExplicitSelection = asArray(select.options).some(function (option) {
        return option.defaultSelected && option.value !== "";
      });
      sortSelectOptions(select);
      if (!hasExplicitSelection) {
        var current = selectedOption(select);
        if (current && current.value !== "") {
          select.selectedIndex = -1;
        }
      }

      select.dataset.lbbSearchableReady = "1";
      select.classList.add("visually-hidden");
      select.setAttribute("tabindex", "-1");
      select.setAttribute("aria-hidden", "true");

      // A hidden required control cannot be focused for native validation and
      // would throw "not focusable". Track it and validate on submit ourselves.
      var wasRequired = select.required;
      if (wasRequired) select.required = false;

      var uid = "lbb-select-" + ++uidCounter;

      var wrapper = doc.createElement("div");
      wrapper.className = "lbb-select dropdown";
      if (select.classList.contains("w-auto")) wrapper.classList.add("w-auto");
      if (select.style.width) wrapper.style.width = select.style.width;
      if (select.style.minWidth) wrapper.style.minWidth = select.style.minWidth;

      var toggle = doc.createElement("button");
      toggle.type = "button";
      toggle.className = "form-select lbb-select-toggle text-start";
      if (select.classList.contains("form-select-sm")) toggle.classList.add("form-select-sm");
      if (select.classList.contains("form-select-lg")) toggle.classList.add("form-select-lg");
      toggle.id = uid + "-toggle";
      toggle.setAttribute("data-bs-toggle", "dropdown");
      toggle.setAttribute("data-bs-auto-close", "outside");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-haspopup", "listbox");
      toggle.disabled = select.disabled;

      var valueSpan = doc.createElement("span");
      valueSpan.className = "lbb-select-value text-truncate";
      toggle.appendChild(valueSpan);

      var clearBtn = doc.createElement("button");
      clearBtn.type = "button";
      clearBtn.className = "lbb-select-clear";
      clearBtn.setAttribute("aria-label", "Hapus pilihan");
      clearBtn.innerHTML = '<i class="bi bi-x-lg"></i>';

      var menu = doc.createElement("div");
      menu.className = "dropdown-menu lbb-select-menu p-0 shadow";

      var searchWrap = doc.createElement("div");
      searchWrap.className = "p-2 border-bottom";
      searchWrap.innerHTML =
        '<div class="input-group input-group-sm">' +
        '<span class="input-group-text"><i class="bi bi-search"></i></span>' +
        '<input type="search" class="form-control lbb-select-search" ' +
        'placeholder="Cari dalam daftar" autocomplete="off">' +
        "</div>";
      var search = searchWrap.querySelector(".lbb-select-search");
      search.id = uid + "-search";
      search.setAttribute("role", "combobox");
      search.setAttribute("aria-controls", uid + "-listbox");
      search.setAttribute("aria-expanded", "true");
      search.setAttribute("aria-autocomplete", "list");
      if (select.dataset.label) search.setAttribute("aria-label", select.dataset.label);

      var listbox = doc.createElement("div");
      listbox.className = "lbb-select-options list-group list-group-flush";
      listbox.id = uid + "-listbox";
      listbox.setAttribute("role", "listbox");
      if (select.dataset.label) listbox.setAttribute("aria-label", select.dataset.label);

      var footer = doc.createElement("div");
      footer.className = "lbb-select-footer small text-muted px-3 py-2 border-top d-none";

      menu.appendChild(searchWrap);
      menu.appendChild(listbox);
      menu.appendChild(footer);

      select.parentNode.insertBefore(wrapper, select.nextSibling);
      wrapper.appendChild(select);
      wrapper.appendChild(toggle);
      wrapper.appendChild(clearBtn);
      wrapper.appendChild(menu);

      var highlightId = null;

      function syncLabel() {
        var option = selectedOption(select);
        var label = option ? optionText(option) : "";
        if (label && option && option.value !== "") {
          valueSpan.textContent = label;
          toggle.classList.remove("lbb-select-placeholder");
          wrapper.classList.add("lbb-has-value");
        } else {
          valueSpan.textContent = placeholderText(select);
          toggle.classList.add("lbb-select-placeholder");
          wrapper.classList.remove("lbb-has-value");
        }
      }

      function clearInvalid() {
        toggle.classList.remove("is-invalid");
        var feedback = wrapper.querySelector(".invalid-feedback");
        if (feedback) feedback.remove();
      }

      function setHighlight(item) {
        asArray(listbox.querySelectorAll(".lbb-highlight")).forEach(function (node) {
          node.classList.remove("lbb-highlight");
        });
        if (item) {
          item.classList.add("lbb-highlight");
          highlightId = item.id;
          search.setAttribute("aria-activedescendant", item.id);
          item.scrollIntoView({ block: "nearest" });
        } else {
          highlightId = null;
          search.removeAttribute("aria-activedescendant");
        }
      }

      function optionItems() {
        return asArray(listbox.querySelectorAll('[role="option"]'));
      }

      function chooseOption(option) {
        select.value = option.value;
        clearInvalid();
        syncLabel();
        getDropdown().hide();
        toggle.focus();
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }

      function buildOption(option, index) {
        var item = doc.createElement("button");
        item.type = "button";
        item.className = "list-group-item list-group-item-action py-2";
        item.setAttribute("role", "option");
        item.id = uid + "-opt-" + index;
        item.textContent = optionText(option);
        if (option.selected && option.value !== "") {
          item.classList.add("active");
          item.setAttribute("aria-selected", "true");
        } else {
          item.setAttribute("aria-selected", "false");
        }
        item.addEventListener("click", function (event) {
          event.preventDefault();
          chooseOption(option);
        });
        item.addEventListener("mousemove", function () {
          setHighlight(item);
        });
        return item;
      }

      // Re-read options every render so external mutations (option.hidden /
      // option.disabled toggles, innerHTML rebuilds) are always reflected.
      function renderOptions() {
        var keyword = String(search.value || "").toLowerCase().trim();
        listbox.innerHTML = "";
        highlightId = null;
        search.removeAttribute("aria-activedescendant");

        function matches(option) {
          if (option.disabled || option.hidden) return false;
          return !keyword || optionText(option).toLowerCase().indexOf(keyword) !== -1;
        }

        var total = 0;
        var shown = 0;
        var index = 0;
        var firstItem = null;

        function appendOption(option) {
          total += 1;
          if (shown >= RENDER_CAP) return;
          var item = buildOption(option, index++);
          listbox.appendChild(item);
          if (!firstItem) firstItem = item;
          shown += 1;
        }

        asArray(select.children).forEach(function (node) {
          if (node.tagName === "OPTGROUP") {
            var groupMatches = asArray(node.children).filter(matches);
            if (!groupMatches.length) return;
            if (shown < RENDER_CAP) {
              var header = doc.createElement("div");
              header.className = "list-group-item lbb-select-optgroup";
              header.textContent = String(node.label || "").trim();
              listbox.appendChild(header);
            }
            groupMatches.forEach(appendOption);
          } else if (node.tagName === "OPTION") {
            if (matches(node)) appendOption(node);
          }
        });

        if (!total) {
          var empty = doc.createElement("div");
          empty.className = "list-group-item text-muted small";
          empty.textContent = "Tidak ada hasil";
          listbox.appendChild(empty);
          footer.classList.add("d-none");
        } else if (total > shown) {
          footer.textContent =
            "Menampilkan " + shown + " dari " + total +
            " pilihan. Persempit pencarian.";
          footer.classList.remove("d-none");
        } else {
          footer.classList.add("d-none");
        }

        var activeItem = listbox.querySelector('[role="option"].active');
        setHighlight(activeItem || firstItem);
      }

      function moveHighlight(step) {
        var items = optionItems();
        if (!items.length) return;
        var currentIndex = -1;
        items.forEach(function (item, idx) {
          if (item.id === highlightId) currentIndex = idx;
        });
        var next = currentIndex + step;
        if (next < 0) next = 0;
        if (next > items.length - 1) next = items.length - 1;
        setHighlight(items[next]);
      }

      function jumpHighlight(toEnd) {
        var items = optionItems();
        if (!items.length) return;
        setHighlight(toEnd ? items[items.length - 1] : items[0]);
      }

      search.addEventListener("input", renderOptions);
      search.addEventListener("keydown", function (event) {
        switch (event.key) {
          case "ArrowDown":
            event.preventDefault();
            moveHighlight(1);
            break;
          case "ArrowUp":
            event.preventDefault();
            moveHighlight(-1);
            break;
          case "Home":
            event.preventDefault();
            jumpHighlight(false);
            break;
          case "End":
            event.preventDefault();
            jumpHighlight(true);
            break;
          case "Enter":
            event.preventDefault();
            var highlighted = highlightId ? doc.getElementById(highlightId) : null;
            if (highlighted) highlighted.click();
            break;
          case "Escape":
            event.preventDefault();
            getDropdown().hide();
            toggle.focus();
            break;
          default:
            break;
        }
      });

      clearBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var blank = blankOption(select);
        if (blank) {
          select.value = "";
        } else {
          select.selectedIndex = -1;
        }
        clearInvalid();
        syncLabel();
        select.dispatchEvent(new Event("change", { bubbles: true }));
      });

      // Bootstrap Dropdown with a Popper strategy that escapes overflow
      // containers (modals, .table-responsive). autoClose:"outside" keeps the
      // panel open while typing; we close explicitly after a choice.
      var dropdown = null;
      function getDropdown() {
        if (!dropdown) {
          dropdown = new bootstrap.Dropdown(toggle, {
            autoClose: "outside",
            popperConfig: function (base) {
              return Object.assign({}, base, { strategy: "fixed" });
            },
          });
        }
        return dropdown;
      }
      getDropdown();

      toggle.addEventListener("show.bs.dropdown", function () {
        search.value = "";
        renderOptions();
        menu.style.minWidth = toggle.getBoundingClientRect().width + "px";
      });
      toggle.addEventListener("shown.bs.dropdown", function () {
        search.focus();
      });

      // Keep the toggle's disabled state mirrored from the native select.
      function syncDisabled() {
        toggle.disabled = select.disabled;
        wrapper.classList.toggle("lbb-is-disabled", select.disabled);
      }
      var disabledObserver = new win.MutationObserver(syncDisabled);
      disabledObserver.observe(select, {
        attributes: true,
        attributeFilter: ["disabled"],
      });

      function onNativeSync() {
        clearInvalid();
        syncLabel();
      }
      select.addEventListener("change", onNativeSync);
      // clearControl dispatches lbb:refresh-searchable WITHOUT bubbling, so it
      // must be bound directly on the select element (delegation won't catch it).
      select.addEventListener("lbb:refresh-searchable", function () {
        sortSelectOptions(select);
        syncLabel();
      });

      // Submit-time required guard: the native select is hidden, so enforce it.
      var ownerForm = select.form;
      var submitGuard = null;
      if (wasRequired && ownerForm) {
        submitGuard = function (event) {
          if (select.value) {
            clearInvalid();
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          toggle.classList.add("is-invalid");
          if (!wrapper.querySelector(".invalid-feedback")) {
            var feedback = doc.createElement("div");
            feedback.className = "invalid-feedback d-block";
            feedback.textContent = "Wajib dipilih.";
            wrapper.appendChild(feedback);
          }
          toggle.focus();
          getDropdown().show();
        };
        ownerForm.addEventListener("submit", submitGuard);
      }

      select._lbbSearchable = {
        wrapper: wrapper,
        renderOptions: renderOptions,
        syncLabel: syncLabel,
        disabledObserver: disabledObserver,
        submitGuard: submitGuard,
        ownerForm: ownerForm,
        wasRequired: wasRequired,
        onNativeSync: onNativeSync,
      };

      syncDisabled();
      syncLabel();
    }

    function refresh(select) {
      if (!select || select.dataset.lbbSearchableReady !== "1") return;
      var state = select._lbbSearchable;
      if (!state) return;
      sortSelectOptions(select);
      state.syncLabel();
    }

    function destroy(select) {
      var state = select && select._lbbSearchable;
      if (!state) return;
      if (state.disabledObserver) state.disabledObserver.disconnect();
      if (state.submitGuard && state.ownerForm) {
        state.ownerForm.removeEventListener("submit", state.submitGuard);
      }
      if (state.wasRequired) select.required = true;
      select.removeEventListener("change", state.onNativeSync);
      if (state.wrapper && state.wrapper.parentNode) {
        state.wrapper.parentNode.insertBefore(select, state.wrapper);
        state.wrapper.parentNode.removeChild(state.wrapper);
      }
      select.classList.remove("visually-hidden");
      select.removeAttribute("tabindex");
      select.removeAttribute("aria-hidden");
      delete select.dataset.lbbSearchableReady;
      delete select._lbbSearchable;
    }

    function init(rootNode) {
      rootNode = rootNode || doc;
      var scope = rootNode.querySelectorAll ? rootNode : doc;
      var nodes = asArray(scope.querySelectorAll(SELECTOR));
      if (rootNode.tagName === "SELECT" && rootNode.matches && rootNode.matches(SELECTOR)) {
        nodes.push(rootNode);
      }
      nodes.forEach(enhance);
    }

    // Debounced document observer: enhance runtime-injected selects (WhatsApp
    // management tables, Data Manager BOOLEAN edit rows) without per-page wiring.
    function scheduleScan() {
      if (pending) return;
      pending = win.setTimeout(function () {
        pending = null;
        init(doc);
      }, 60);
    }

    function startObserver() {
      if (domObserver || !win.MutationObserver) return;
      domObserver = new win.MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
          var added = mutations[i].addedNodes;
          for (var j = 0; j < added.length; j++) {
            var node = added[j];
            if (node.nodeType !== 1) continue;
            // Ignore our own inserted wrappers to avoid reacting to self-edits.
            if (node.classList && node.classList.contains("lbb-select")) continue;
            if (
              (node.matches && node.matches(SELECTOR)) ||
              (node.querySelector && node.querySelector(SELECTOR))
            ) {
              scheduleScan();
              return;
            }
          }
        }
      });
      domObserver.observe(doc.body, { childList: true, subtree: true });
    }

    function start() {
      bootstrap = win.bootstrap;
      if (doc.readyState === "loading") {
        doc.addEventListener("DOMContentLoaded", function () {
          init(doc);
          startObserver();
        });
      } else {
        init(doc);
        startObserver();
      }
    }

    return {
      init: init,
      enhance: enhance,
      refresh: refresh,
      destroy: destroy,
      start: start,
      sortSelectOptions: sortSelectOptions,
      shouldSortSelectOptions: shouldSortSelectOptions,
      optionText: optionText,
    };
  }

  return {
    createBrowserManager: createBrowserManager,
    sortSelectOptions: sortSelectOptions,
    shouldSortSelectOptions: shouldSortSelectOptions,
    optionText: optionText,
  };
});
