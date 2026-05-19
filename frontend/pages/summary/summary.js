import { getProjectDates, getProject } from "../../utils/api";

Page({
  data: {
    dates: [],
    currentDate: "",
    currentLabel: "今天",
    showDates: false,
    project: null,
    loading: true,
    noProject: false,
  },

  onLoad() {
    this.loadDates();
  },

  toggleDates() {
    this.setData({ showDates: !this.data.showDates });
  },

  async loadDates() {
    try {
      const today = getApp().globalData.today;

      const projectDates = await getProjectDates();
      const formatted = projectDates.map((d) => ({
        ...d,
        label: this._formatLabel(d.date, today),
      }));

      // 确保今天始终在列表中
      const hasToday = formatted.some((d) => d.date === today);
      if (!hasToday) {
        formatted.unshift({ date: today, label: "今天" });
      }

      const currentDate = today;
      const current = formatted.find((d) => d.date === today);

      this.setData({
        dates: formatted,
        currentDate,
        currentLabel: current ? current.label : "今天",
      });

      this.loadProject(currentDate);
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  async loadProject(date) {
    if (!date) return;
    this.setData({ loading: true, project: null, noProject: false });

    try {
      const result = await getProject(date);
      this.setData({ project: result, loading: false });
    } catch (e) {
      if (e.msg && (e.msg.includes("暂无") || e.msg.includes("404"))) {
        this.setData({ loading: false, noProject: true });
      } else {
        this.setData({ loading: false, noProject: true });
      }
    }
  },

  switchDate(e) {
    const { date } = e.currentTarget.dataset;
    if (date === this.data.currentDate) {
      this.setData({ showDates: false });
      return;
    }
    const target = this.data.dates.find((d) => d.date === date);
    this.setData({
      currentDate: date,
      currentLabel: target ? target.label : date,
      showDates: false,
    });
    this.loadProject(date);
  },

  _formatLabel(dateStr, today) {
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
  },
});
