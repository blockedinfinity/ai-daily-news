import { getAvailableDates, getSummary, generateSummary } from "../../utils/api";

Page({
  data: {
    dates: [],
    currentDate: "",
    content: "",
    loading: true,
    noNews: false,
    generating: false,
  },

  onLoad() {
    this.loadDates();
  },

  async loadDates() {
    try {
      const dates = await getAvailableDates();
      const today = getApp().globalData.today;

      const formatted = dates.map((d) => ({
        ...d,
        label: this.formatLabel(d.date, today),
      }));

      this.setData({
        dates: formatted,
        currentDate: formatted.length > 0 ? formatted[0].date : today,
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
      if (e.msg && e.msg.includes("暂无摘要")) {
        this.setData({ loading: false, content: "" });
      } else {
        this.setData({ loading: false, noNews: true });
      }
    }
  },

  switchDate(e) {
    const { date } = e.currentTarget.dataset;
    if (date === this.data.currentDate) return;
    this.setData({ currentDate: date, content: "" });
    this.loadSummary(date);
  },

  async generate() {
    const date = this.data.currentDate;
    if (!date || this.data.generating) return;

    this.setData({ generating: true });
    try {
      const result = await generateSummary(date);
      this.setData({ content: result.content, generating: false });
      wx.showToast({ title: "摘要生成成功", icon: "success" });
    } catch (e) {
      this.setData({ generating: false });
      wx.showToast({ title: e.msg || "生成失败", icon: "none" });
    }
  },

  formatLabel(dateStr, today) {
    if (dateStr === today) return "今天";
    const d = new Date(dateStr);
    const weekDays = ["日", "一", "二", "三", "四", "五", "六"];
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr =
      yesterday.getFullYear() +
      "-" +
      String(yesterday.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(yesterday.getDate()).padStart(2, "0");

    if (dateStr === yesterdayStr) return "昨天";
    return `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")} 周${weekDays[d.getDay()]}`;
  },
});
