import { getNewsByDate, getAvailableDates } from "../../utils/api";

const app = getApp();
const PAGE_SIZE = 5;

Page({
  data: {
    dates: [],
    currentDate: "",
    currentLabel: "今天",
    currentCount: 0,
    showDates: false,
    newsList: [],
    loading: true,
    error: "",
    displayCount: PAGE_SIZE,
    allLoaded: false,
    loadingMore: false,
  },

  _allItems: [],

  onLoad() {
    this.loadDates();
  },

  onShow() {
    if (this.data.currentDate) {
      this.loadNews(this.data.currentDate, true);
    }
  },

  onPullDownRefresh() {
    wx.showNavigationBarLoading();
    if (this.data.currentDate) {
      this.loadNews(this.data.currentDate)
        .finally(() => {
          wx.stopPullDownRefresh();
          wx.hideNavigationBarLoading();
        });
    } else {
      wx.stopPullDownRefresh();
      wx.hideNavigationBarLoading();
    }
  },

  onReachBottom() {
    if (this.data.allLoaded || this.data.loadingMore || this.data.loading) return;
    this.loadMore();
  },

  toggleDates() {
    this.setData({ showDates: !this.data.showDates });
  },

  async loadDates() {
    try {
      const dates = await getAvailableDates();
      const today = app.globalData.today;

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

      await this.loadNews(currentDate);
    } catch {
      this.setData({ loading: false, error: "加载日期失败" });
    }
  },

  async loadNews(date, silent = false) {
    if (!date) return;
    if (!silent) this.setData({ loading: true, error: "" });

    try {
      const result = await getNewsByDate(date);
      this._allItems = result.items || [];
      const displayCount = Math.min(PAGE_SIZE, this._allItems.length);
      this.setData({
        newsList: this._allItems.slice(0, displayCount),
        displayCount,
        allLoaded: displayCount >= this._allItems.length,
        loading: false,
        error: "",
      });
    } catch {
      if (!silent) {
        this.setData({ error: "加载失败，请重试", loading: false });
      }
    }
  },

  loadMore() {
    const nextCount = this.data.displayCount + PAGE_SIZE;
    if (nextCount >= this._allItems.length) {
      this.setData({
        newsList: this._allItems,
        displayCount: this._allItems.length,
        allLoaded: true,
      });
      return;
    }
    this.setData({ loadingMore: true });
    setTimeout(() => {
      this.setData({
        newsList: this._allItems.slice(0, nextCount),
        displayCount: nextCount,
        loadingMore: false,
      });
    }, 300);
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
    this.loadNews(date);
  },

  goDetail(e) {
    const { id } = e.currentTarget.dataset;
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
