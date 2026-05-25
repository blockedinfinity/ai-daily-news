export function formatDate(dateStr) {
  const d = new Date(dateStr);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function formatTime(dateStr) {
  const d = new Date(dateStr);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function isToday(dateStr) {
  return formatDate(dateStr) === formatDate(new Date());
}

/**
 * 格式化日期标签（今天 / 昨天 / MM/DD 周X）
 * @param {string} dateStr - 日期字符串 YYYY-MM-DD
 * @param {string} today - 今天的日期字符串 YYYY-MM-DD
 * @returns {string}
 */
export function formatLabel(dateStr, today) {
  if (dateStr === today) return "今天";
  const weekDays = ["日", "一", "二", "三", "四", "五", "六"];
  const d = new Date(dateStr);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr =
    yesterday.getFullYear() +
    "-" +
    String(yesterday.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(yesterday.getDate()).padStart(2, "0");
  if (dateStr === yesterdayStr) return "昨天";
  return (
    String(d.getMonth() + 1).padStart(2, "0") +
    "/" +
    String(d.getDate()).padStart(2, "0") +
    " 周" +
    weekDays[d.getDay()]
  );
}
