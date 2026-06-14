/* Identity helpers shared by the landing and room pages.
 *
 * user_id: stable per browser, survives reloads and reconnects. This is what
 *          the server keys players by. Lives in localStorage.
 * name:    per session (per tab lifetime). Collected on the landing page or
 *          via the room page's name prompt. Lives in sessionStorage.
 */
window.Identity = (function () {
  "use strict";

  const UID_KEY = "draw_hunt_uid";
  const NAME_KEY = "draw_hunt_name";

  function getUserId() {
    let id = localStorage.getItem(UID_KEY);
    if (!id) {
      id =
        "u_" +
        (crypto.randomUUID
          ? crypto.randomUUID()
          : Date.now().toString(36) + Math.random().toString(36).slice(2));
      localStorage.setItem(UID_KEY, id);
    }
    return id;
  }

  function getName() {
    return (sessionStorage.getItem(NAME_KEY) || "").trim();
  }

  function setName(name) {
    sessionStorage.setItem(NAME_KEY, (name || "").trim());
  }

  return { getUserId, getName, setName };
})();