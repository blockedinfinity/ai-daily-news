import { getNewsByDate, getAvailableDates } from "../../utils/api";

const app = getApp();

Page({
  data: {
    dates: [],
    currentDate: "",
    newsList: [],
    loading: true,
    error: "",
  },

  onLoad() {
    this.loadDates();
  },

  onShow() {
    // 从详情页返回时刷新列表
    if (this.data.currentDate) {
      this.loadNews(this.data.currentDate, true);
    }
  },

  onPullDownRefresh() {
    if (this.data.currentDate) {
      this.loadNews(this.data.currentDate)
        .then(() => wx.stopPullDownRefresh())
        .catch(() => wx.stopPullDownRefresh());
    }
  },

  async loadDates() {
    try {
      const dates = await getAvailableDates();
      const today = app.globalData.today;

      const formatted = dates.map((d) => ({
        ...d,
        label: this._formatLabel(d.date, today),
      }));

      this.setData({
        dates: formatted,
        currentDate: formatted.length > 0 ? formatted[0].date : today,
      });

      await this.loadNews(this.data.currentDate);
    } catch {
      this.setData({ loading: false, error: "加载日期失败" });
    }
  },

  async loadNews(date, silent = false) {
    if (!date) return;
    if (!silent) this.setData({ loading: true, error: "" });

    try {
      const result = await getNewsByDate(date);
      // 限制最多显示 5 篇
      const items = (result.items || []).slice(0, 5);
      this.setData({ newsList: items, loading: false, error: "" });
    } catch {
      if (!silent) {
        this.setData({ error: "加载失败，请重试", loading: false });
      }
    }
  },

  switchDate(e) {
    const { date } = e.currentTarget.dataset;
    if (date === this.data.currentDate) return;
    this.setData({ currentDate: date });
    this.loadNews(date);
  },

  goDetail(e) {
    const { id, title, summary, url } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`,
    });
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
