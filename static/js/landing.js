/* Landing page: create a room or join one with a code.
 *
 * Create: POST /api/create-room to mint a code, then navigate to /room/<code>.
 * Join:   validate the code locally, then navigate to /room/<code>.
 * In both cases the name is stashed in sessionStorage so the room page has it.
 * No socket is opened here — all real-time work happens on the room page.
 */
(function () {
  "use strict";

  const nameInput = document.getElementById("name-input");
  const codeInput = document.getElementById("code-input");
  const createBtn = document.getElementById("create-btn");
  const joinBtn = document.getElementById("join-btn");
  const errorEl = document.getElementById("landing-error");

  const CODE_RE = /^[A-HJ-NP-Z]{4}$/; // matches the server alphabet (no I/O), length 4

  function showError(msg) {
    errorEl.textContent = msg;
  }

  function requireName() {
    const name = nameInput.value.trim();
    if (!name) {
      showError("Enter a name first.");
      nameInput.focus();
      return null;
    }
    return name;
  }

  function goToRoom(code) {
    window.location.href = "/room/" + code;
  }

  createBtn.addEventListener("click", function () {
    showError("");
    const name = requireName();
    if (!name) return;

    Identity.setName(name);
    createBtn.disabled = true;
    createBtn.textContent = "Creating…";

    fetch("/api/create-room", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: Identity.getUserId() }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("create failed");
        return r.json();
      })
      .then(function (data) {
        if (data && data.code) goToRoom(data.code);
        else throw new Error("no code returned");
      })
      .catch(function () {
        showError("Couldn't create a room. Try again.");
        createBtn.disabled = false;
        createBtn.textContent = "Create a room";
      });
  });

  joinBtn.addEventListener("click", function () {
    showError("");
    const name = requireName();
    if (!name) return;

    const code = codeInput.value.trim().toUpperCase();
    if (!CODE_RE.test(code)) {
      showError("That code doesn't look right — 4 letters, like WXYZ.");
      codeInput.focus();
      return;
    }
    Identity.setName(name);
    goToRoom(code);
  });

  // Enter key submits the join row.
  codeInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") joinBtn.click();
  });
  // Uppercase the code as it's typed.
  codeInput.addEventListener("input", function () {
    codeInput.value = codeInput.value.toUpperCase();
  });

  // Pre-fill a remembered name for convenience.
  const remembered = Identity.getName();
  if (remembered) nameInput.value = remembered;
})();