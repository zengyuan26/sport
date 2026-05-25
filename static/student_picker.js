// Shared student picker: search + recent/frequent students via localStorage

var RECENT_KEY = 'fitness_recent_students';
var MAX_RECENT = 6;

function getRecentStudents() {
  try {
    var raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveRecentStudents(list) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch (e) {}
}

function recordStudentPick(id, name, emoji, photo) {
  var list = getRecentStudents();
  var found = null;
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === id) { found = list[i]; break; }
  }
  if (found) {
    found.count = (found.count || 0) + 1;
    found.lastUsed = Date.now();
    found.name = name;
    found.emoji = emoji || found.emoji;
    found.photo = photo || found.photo;
  } else {
    list.push({ id: id, name: name, emoji: emoji || '', photo: photo || '', count: 1, lastUsed: Date.now() });
  }
  list.sort(function(a, b) { return (b.count || 0) - (a.count || 0); });
  if (list.length > 20) list = list.slice(0, 20);
  saveRecentStudents(list);
}

// Render a "常用" section into a container element
// students: array of {id, name, emoji, photo} from recent storage
// onClick: function(id, name, emoji) called on click
// renderTo: DOM element to append chips into, or null to return HTML string
function renderRecentChips(students, onClick, renderTo) {
  if (!students || students.length === 0) return '';
  var html = '<div style="font-size:12px;color:#8E8E93;margin-bottom:6px;">🕐 常用学员</div>';
  html += '<div class="recent-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;">';
  for (var i = 0; i < students.length; i++) {
    var s = students[i];
    html += '<div class="recent-chip" data-sid="' + s.id + '" data-sname="' + s.name + '" data-semoji="' + (s.emoji || '') + '" style="display:flex;align-items:center;gap:6px;background:#2C2C2E;border-radius:20px;padding:6px 12px;cursor:pointer;font-size:13px;font-weight:600;transition:opacity 0.15s;">';
    if (s.photo) {
      html += '<img src="' + s.photo + '" style="width:22px;height:22px;border-radius:50%;object-fit:cover;">';
    } else if (s.emoji) {
      html += '<span style="font-size:18px;">' + s.emoji + '</span>';
    }
    html += '<span>' + s.name + '</span>';
    html += '</div>';
  }
  html += '</div>';
  if (renderTo) {
    renderTo.insertAdjacentHTML('beforeend', html);
    // Bind clicks
    var chips = renderTo.querySelectorAll('.recent-chip');
    for (var j = 0; j < chips.length; j++) {
      (function(chip) {
        chip.addEventListener('click', function() {
          onClick(
            parseInt(chip.getAttribute('data-sid')),
            chip.getAttribute('data-sname'),
            chip.getAttribute('data-semoji')
          );
        });
      })(chips[j]);
    }
  }
  return html;
}

// Filter DOM elements by search query
// items: NodeList or array of DOM elements
// getText: function(el) returns the text to match against
// query: search string
function filterItems(items, getText, query) {
  var q = (query || '').toLowerCase().trim();
  for (var i = 0; i < items.length; i++) {
    var el = items[i];
    if (!q) {
      el.style.display = '';
      continue;
    }
    var txt = getText(el).toLowerCase();
    el.style.display = txt.indexOf(q) >= 0 ? '' : 'none';
  }
}
