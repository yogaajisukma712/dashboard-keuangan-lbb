(function (root, factory) {
  var core = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = core;
  }
  if (root && root.document) {
    root.LbbPersistentFilters = core.createBrowserManager(root);
    root.LbbPersistentFilters.start();
  }
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  var STORAGE_PREFIX = "lbb:filters:v3:";
  var LEGACY_PREFIX = "lbb:table-filter:";
  var SKIPPED_NAMES = ["csrf_token", "page", "reset", "reset_filters"];
  var SUMMARY_SKIPPED_NAMES = SKIPPED_NAMES.concat(["per_page"]);

  function asArray(value) {
    return Array.prototype.slice.call(value || []);
  }

  function stableHash(value) {
    var hash = 5381;
    String(value || "").split("").forEach(function (character) {
      hash = ((hash << 5) + hash) ^ character.charCodeAt(0);
    });
    return (hash >>> 0).toString(36);
  }

  function normalizedValues(value) {
    if (Array.isArray(value)) {
      return value
        .map(function (item) {
          return String(item == null ? "" : item).trim();
        })
        .filter(Boolean);
    }
    var normalized = String(value == null ? "" : value).trim();
    return normalized ? [normalized] : [];
  }

  function mergeRestoredSearch(search, restorations) {
    var params = new URLSearchParams(search || "");
    var changed = false;
    (restorations || []).forEach(function (values) {
      Object.keys(values || {}).forEach(function (name) {
        if (SKIPPED_NAMES.includes(name) || params.has(name)) return;
        var items = normalizedValues(values[name]);
        if (!items.length) return;
        items.forEach(function (item) {
          params.append(name, item);
        });
        changed = true;
      });
    });
    if (changed) {
      params.delete("page");
    }
    return {
      changed: changed,
      search: params.toString(),
    };
  }

  function buildStorageKey(userId, pathname, actionPath, identity) {
    var scope = [
      String(userId || "guest"),
      String(pathname || "/"),
      String(actionPath || pathname || "/"),
      String(identity || "filter"),
    ].join("|");
    return STORAGE_PREFIX + stableHash(scope);
  }

  function createBrowserManager(win) {
    var doc = win.document;
    var started = false;
    var storageReady = false;
    var suppressNextInitialSave = false;

    function storageAvailable() {
      try {
        var key = STORAGE_PREFIX + "test";
        win.localStorage.setItem(key, "1");
        win.localStorage.removeItem(key);
        return true;
      } catch (_error) {
        return false;
      }
    }

    function getUserId() {
      return doc.body && doc.body.dataset.lbbFilterUser
        ? doc.body.dataset.lbbFilterUser
        : "guest";
    }

    function isSkippedControl(control) {
      var type = String(control.type || "").toLowerCase();
      return (
        !control.name ||
        control.disabled ||
        control.dataset.lbbFilterIgnore === "true" ||
        SKIPPED_NAMES.includes(control.name) ||
        ["button", "submit", "reset", "file", "password", "image"].includes(type)
      );
    }

    function getControls(form) {
      return asArray(
        form.querySelectorAll("input[name], select[name], textarea[name]"),
      ).filter(function (control) {
        return !isSkippedControl(control);
      });
    }

    function getControlNames(form) {
      return getControls(form)
        .map(function (control) {
          return control.name;
        })
        .filter(function (name, index, names) {
          return names.indexOf(name) === index;
        })
        .sort();
    }

    function isFilterForm(form) {
      if (String(form.method || "get").toLowerCase() !== "get") return false;
      if (form.dataset.lbbFilterPersist === "false") return false;
      var action = new URL(
        form.getAttribute("action") || win.location.pathname,
        win.location.href,
      );
      if (action.origin !== win.location.origin) return false;
      return getControlNames(form).some(function (name) {
        return !SUMMARY_SKIPPED_NAMES.includes(name);
      });
    }

    function formIdentity(form) {
      var names = getControlNames(form);
      return form.id ? "id:" + form.id : "fields:" + names.join(",");
    }

    function formKey(form) {
      var action = new URL(
        form.getAttribute("action") || win.location.pathname,
        win.location.href,
      );
      return buildStorageKey(
        getUserId(),
        win.location.pathname,
        action.pathname,
        formIdentity(form),
      );
    }

    function readForm(form) {
      var values = {};
      var controls = getControls(form);
      getControlNames(form).forEach(function (name) {
        var group = controls.filter(function (control) {
          return control.name === name;
        });
        var first = group[0];
        if (!first) return;
        if (first.type === "checkbox" || first.type === "radio") {
          values[name] = group
            .filter(function (control) {
              return control.checked;
            })
            .map(function (control) {
              return control.value || "1";
            });
          return;
        }
        if (first.multiple) {
          values[name] = asArray(first.selectedOptions).map(function (option) {
            return option.value;
          });
          return;
        }
        values[name] = first.value || "";
      });
      return values;
    }

    function loadForm(form) {
      try {
        var raw = win.localStorage.getItem(formKey(form));
        if (!raw) return null;
        var payload = JSON.parse(raw);
        return payload && payload.values ? payload.values : null;
      } catch (_error) {
        win.localStorage.removeItem(formKey(form));
        return null;
      }
    }

    function saveForm(form) {
      if (!storageReady || !isFilterForm(form)) return;
      win.localStorage.setItem(
        formKey(form),
        JSON.stringify({
          path: win.location.pathname,
          userId: getUserId(),
          values: readForm(form),
          updatedAt: new Date().toISOString(),
        }),
      );
    }

    function clearPage() {
      if (!storageReady) return;
      Object.keys(win.localStorage).forEach(function (key) {
        if (key.indexOf(STORAGE_PREFIX) !== 0) return;
        try {
          var payload = JSON.parse(win.localStorage.getItem(key));
          if (
            payload &&
            payload.path === win.location.pathname &&
            payload.userId === getUserId()
          ) {
            win.localStorage.removeItem(key);
          }
        } catch (_error) {
          if (key.indexOf(LEGACY_PREFIX) === 0) {
            win.localStorage.removeItem(key);
          }
        }
      });
      var controlPrefix =
        STORAGE_PREFIX +
        "control:" +
        stableHash(getUserId() + "|" + win.location.pathname) +
        ":";
      Object.keys(win.localStorage).forEach(function (key) {
        if (key.indexOf(controlPrefix) === 0) {
          win.localStorage.removeItem(key);
        }
      });
      getFilterForms().forEach(function (form) {
        win.localStorage.removeItem(formKey(form));
      });
    }

    function getFilterForms(root) {
      return asArray((root || doc).querySelectorAll("form")).filter(isFilterForm);
    }

    function restoreFromStorage(forms) {
      var url = new URL(win.location.href);
      if (url.searchParams.get("reset_filters") === "1") {
        clearPage();
        suppressNextInitialSave = true;
        url.searchParams.delete("reset_filters");
        win.history.replaceState({}, "", url.toString());
        return false;
      }

      var restorations = forms
        .filter(function (form) {
          var action = new URL(
            form.getAttribute("action") || win.location.pathname,
            win.location.href,
          );
          return action.pathname === url.pathname;
        })
        .map(loadForm)
        .filter(Boolean);
      var merged = mergeRestoredSearch(url.search, restorations);
      if (!merged.changed) return false;
      url.search = merged.search;
      win.location.replace(url.toString());
      return true;
    }

    function buildUrlFromForm(form) {
      var url = new URL(
        form.getAttribute("action") || win.location.pathname,
        win.location.href,
      );
      var params = new URLSearchParams();
      new FormData(form).forEach(function (value, name) {
        if (SKIPPED_NAMES.includes(name)) return;
        var normalized = String(value == null ? "" : value).trim();
        if (normalized) params.append(name, normalized);
      });
      url.search = params.toString();
      return url;
    }

    function controlLabel(form, name) {
      var control = getControls(form).find(function (item) {
        return item.name === name;
      });
      if (!control) return name.replace(/_/g, " ");
      var label = control.id
        ? form.querySelector('label[for="' + CSS.escape(control.id) + '"]')
        : null;
      if (!label) {
        var container = control.closest(
          ".col, [class*='col-'], .form-group, .mb-2, .mb-3",
        );
        label = container ? container.querySelector("label") : null;
      }
      return String(label ? label.textContent : name.replace(/_/g, " "))
        .replace(/\s+/g, " ")
        .trim();
    }

    function displayValue(form, name, rawValue) {
      var control = getControls(form).find(function (item) {
        return item.name === name;
      });
      if (!control) return rawValue;
      if (control.tagName === "SELECT") {
        var option = asArray(control.options).find(function (item) {
          return item.value === rawValue;
        });
        return option ? String(option.textContent).trim() : rawValue;
      }
      return rawValue;
    }

    function clearControl(form, name) {
      getControls(form)
        .filter(function (control) {
          return control.name === name;
        })
        .forEach(function (control) {
          if (control.type === "checkbox" || control.type === "radio") {
            control.checked = false;
          } else if (control.multiple) {
            asArray(control.options).forEach(function (option) {
              option.selected = false;
            });
          } else {
            control.value = "";
          }
          control.dispatchEvent(new Event("lbb:refresh-searchable"));
        });
    }

    function navigate(form, url, replace) {
      saveForm(form);
      if (
        win.LbbFilterUi &&
        form.dataset.lbbFilterTargets &&
        typeof win.LbbFilterUi.request === "function"
      ) {
        win.LbbFilterUi.request(form, url, replace ? "replace" : "push");
        return;
      }
      if (replace) {
        win.location.replace(url.toString());
      } else {
        win.location.assign(url.toString());
      }
    }

    function renderSummary(form) {
      var current = form.querySelector(".lbb-filter-memory-bar");
      if (current) current.remove();

      var params = new URLSearchParams(win.location.search);
      var names = getControlNames(form).filter(function (name) {
        return !SUMMARY_SKIPPED_NAMES.includes(name) && params.has(name);
      });
      var active = [];
      names.forEach(function (name) {
        params.getAll(name).forEach(function (value) {
          if (String(value || "").trim()) {
            active.push({
              name: name,
              label: controlLabel(form, name),
              value: displayValue(form, name, value),
            });
          }
        });
      });
      if (!active.length) return;

      var bar = doc.createElement("div");
      bar.className =
        "lbb-filter-memory-bar" +
        (form.classList.contains("row") ? " col-12" : "");

      var label = doc.createElement("span");
      label.className = "lbb-filter-memory-label";
      label.innerHTML = '<i class="bi bi-funnel-fill"></i><span>Filter aktif</span>';
      bar.appendChild(label);

      active.forEach(function (item) {
        var chip = doc.createElement("span");
        chip.className = "lbb-filter-chip";

        var text = doc.createElement("span");
        text.className = "lbb-filter-chip-text";
        text.textContent = item.label + ": " + item.value;
        chip.appendChild(text);

        var remove = doc.createElement("button");
        remove.type = "button";
        remove.className = "lbb-filter-chip-remove";
        remove.title = "Hapus filter " + item.label;
        remove.setAttribute("aria-label", remove.title);
        remove.innerHTML = '<i class="bi bi-x-lg"></i>';
        remove.addEventListener("click", function () {
          clearControl(form, item.name);
          navigate(form, buildUrlFromForm(form), false);
        });
        chip.appendChild(remove);
        bar.appendChild(chip);
      });

      var existingReset = form.id
        ? doc.querySelector(
            '[data-lbb-filter-reset="' + CSS.escape(form.id) + '"]',
          )
        : null;
      if (!existingReset) {
        var reset = doc.createElement("button");
        reset.type = "button";
        reset.className = "btn btn-outline-secondary btn-sm lbb-filter-reset";
        reset.dataset.lbbFilterReset = form.id || "1";
        reset.title = "Reset semua filter";
        reset.innerHTML =
          '<i class="bi bi-arrow-counterclockwise me-1"></i><span>Reset</span>';
        reset.addEventListener("click", function () {
          clearPage();
          var url = new URL(
            form.getAttribute("action") || win.location.pathname,
            win.location.href,
          );
          url.searchParams.set("reset_filters", "1");
          navigate(form, url, false);
        });
        bar.appendChild(reset);
      }
      form.appendChild(bar);
    }

    function bindForm(form) {
      form.classList.add("lbb-filter-managed");
      if (form.dataset.lbbPersistenceBound === "1") {
        renderSummary(form);
        return;
      }
      form.dataset.lbbPersistenceBound = "1";
      form.addEventListener("submit", function () {
        saveForm(form);
      });
      form.addEventListener("change", function () {
        saveForm(form);
        renderSummary(form);
      });
      form.addEventListener("input", function () {
        saveForm(form);
      });
      renderSummary(form);
    }

    function standaloneKey(control) {
      var pageScope = stableHash(getUserId() + "|" + win.location.pathname);
      return (
        STORAGE_PREFIX +
        "control:" +
        pageScope +
        ":" +
        stableHash(control.id)
      );
    }

    function bindStandaloneControls(root) {
      asArray(
        (root || doc).querySelectorAll(
          "#main-content input[id]:not([name]), #main-content select[id]:not([name]), main input[id]:not([name]), main select[id]:not([name])",
        ),
      )
        .filter(function (control) {
          var text = [
            control.id,
            control.placeholder || "",
            control.getAttribute("aria-label") || "",
          ]
            .join(" ")
            .toLowerCase();
          return /(filter|search|cari|saring|quick)/.test(text);
        })
        .forEach(function (control) {
          if (control.dataset.lbbPersistenceBound === "1") return;
          control.dataset.lbbPersistenceBound = "1";
          var key = standaloneKey(control);
          var saved = win.localStorage.getItem(key);
          if (saved !== null) {
            control.value = saved;
            control.dispatchEvent(new Event("input", { bubbles: true }));
          }
          ["input", "change"].forEach(function (eventName) {
            control.addEventListener(eventName, function () {
              win.localStorage.setItem(key, control.value || "");
            });
          });
        });
    }

    function migrateLegacyStorage() {
      Object.keys(win.localStorage).forEach(function (key) {
        if (key.indexOf(LEGACY_PREFIX) === 0) {
          win.localStorage.removeItem(key);
        }
      });
    }

    function init(root, allowRestore) {
      var forms = getFilterForms(root || doc);
      if (allowRestore !== false && restoreFromStorage(forms)) return false;
      var shouldSave = !suppressNextInitialSave;
      suppressNextInitialSave = false;
      forms.forEach(function (form) {
        if (shouldSave) saveForm(form);
        bindForm(form);
      });
      bindStandaloneControls(root || doc);
      return true;
    }

    function start() {
      if (started) return;
      started = true;
      storageReady = storageAvailable();
      if (!storageReady) return;
      migrateLegacyStorage();

      doc.addEventListener("DOMContentLoaded", function () {
        init(doc, true);
      });
      doc.addEventListener("lbb:filter-updated", function () {
        init(doc, false);
      });
      doc.addEventListener(
        "click",
        function (event) {
          var reset = event.target.closest("[data-lbb-filter-reset]");
          if (reset) clearPage();
        },
        true,
      );
    }

    return {
      start: start,
      init: init,
      save: saveForm,
      clearPage: clearPage,
      buildUrl: buildUrlFromForm,
    };
  }

  return {
    STORAGE_PREFIX: STORAGE_PREFIX,
    buildStorageKey: buildStorageKey,
    mergeRestoredSearch: mergeRestoredSearch,
    normalizedValues: normalizedValues,
    stableHash: stableHash,
    createBrowserManager: createBrowserManager,
  };
});
