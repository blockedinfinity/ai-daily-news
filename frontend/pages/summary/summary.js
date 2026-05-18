import { getAvailableDates, getSummary, generateSummary } from "../../utils/api";

Page({
  data: {
    dates: [],
    currentDate: "",
    currentLabel: "今天",
    currentCount: 0,
    showDates: false,
    content: "",
    loading: true,
    noNews: false,
    generating: false,
  },

  onLoad() {
    this.loadDates();
  },

  toggleDates() {
    this.setData({ showDates: !this.data.showDates });
  },

  async loadDates() {
    try {
      const dates = await getAvailableDates();
      const today = getApp().globalData.today;

      const formatted = dates.map((d) => ({
        ...d,
        label: this._formatLabel(d.date, today),
      }));

      const currentDate = formatted.length > 0 ? formatted[0].date : today;
      const current = formatted.find((d) => d.date === currentDate);

      this.setData({
        dates: formatted,
        currentDate,
        currentLabel: current ? current.label : "今天",
        currentCount: current ? (current.count || 0) : 0,
      });

      if (this.data.currentDate) {
        this.loadSummary(this.data.currentDate);
      } else {
        this.setData({ loading: false, noNews: true });
      }
    } catch {
      this.setData({ loading: false });
    }
  },

  async loadSummary(date) {
    if (!date) return;
    this.setData({ loading: true, content: "", noNews: false });

    try {
      const result = await getSummary(date);
      this.setData({ content: result.content, loading: false });
    } catch (e) {
      if (e.msg && e.msg.includes("暂无")) {
        this.setData({ loading: false, content: "" });
      } else {
        this.setData({ loading: false, noNews: true });
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
      currentCount: target ? (target.count || 0) : 0,
      showDates: false,
    });
    this.loadSummary(date);
  },

  async generate() {
    const date = this.data.currentDate;
    if (!date || this.data.generating) return;

    this.setData({ generating: true });
    try {
      const result = await generateSummary(date);
      this.setData({ content: result.content, generating: false });
      wx.showToast({ title: "总结生成成功", icon: "success" });
    } catch (e) {
      this.setData({ generating: false });
      wx.showToast({ title: e.msg || "生成失败", icon: "none" });
    }
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
