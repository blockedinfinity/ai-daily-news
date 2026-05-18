import { getAvailableDates, getSummary, generateSummary } from "../../utils/api";

Page({
  data: {
    currentDate: "",
    currentLabel: "今天",
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

      // 只取今天
      const todayItem = dates.find((d) => d.date === today);
      const currentDate = todayItem ? todayItem.date : (dates.length > 0 ? dates[0].date : today);

      this.setData({
        currentDate,
        currentLabel: this._formatLabel(currentDate, today),
      });

      this.loadSummary(currentDate);
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
