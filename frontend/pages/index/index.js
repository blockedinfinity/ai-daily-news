import { getNewsByDate, getAvailableDates } from "../../utils/api";
import { formatLabel } from "../../utils/util";

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
    initialLoadDone: false,   // 标记初始加载是否完成
    lastLoadTime: 0,           // 上次加载时间戳（毫秒）
  },

  _allItems: [],
  _loadingDate: "", // 当前正在加载的日期，用于防竞态

  onLoad() {
    this.loadDates();
  },

  onShow() {
    const now = Date.now();
    // 只在初始加载完成后且距上次加载超过 30 秒时才静默刷新
    if (this.data.initialLoadDone && this.data.currentDate && now - this.data.lastLoadTime > 30 * 1000) {
      this.setData({ lastLoadTime: now });
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
        label: formatLabel(d.date, today),
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
    this._loadingDate = date;
    if (!silent) this.setData({ loading: true, error: "" });

    try {
      const result = await getNewsByDate(date);
      if (date !== this._loadingDate) return; // 丢弃过期响应（用户已切换日期）
      this._allItems = result.items || [];
      const displayCount = Math.min(PAGE_SIZE, this._allItems.length);
      this.setData({
        newsList: this._allItems.slice(0, displayCount),
        displayCount,
        allLoaded: displayCount >= this._allItems.length,
        loading: false,
        error: "",
        initialLoadDone: true,
        lastLoadTime: Date.now(),
      });
    } catch {
      if (!silent) {
        this.setData({ error: "加载失败，请重试", loading: false });
      }
    }
  },

  loadMore() {
    this.setData({ loadingMore: true });
    const nextCount = this.data.displayCount + PAGE_SIZE;
    if (nextCount >= this._allItems.length) {
      this.setData({
        newsList: this._allItems,
        displayCount: this._allItems.length,
        allLoaded: true,
        loadingMore: false,
      });
      return;
    }
    this.setData({
      newsList: this._allItems.slice(0, nextCount),
      displayCount: nextCount,
      loadingMore: false,
    });
  },

  onRetry() {
    if (this.data.currentDate) {
      this.loadNews(this.data.currentDate);
    } else {
      this.loadDates();
    }
  },

  async switchDate(e) {
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
    await this.loadNews(date);
  },

  goDetail(e) {
    const { id } = e.currentTarget.dataset;
    wx.navigateTo({
      url: `/pages/detail/detail?id=${id}`,
    });
  },

  /** 分享给微信好友 */
  onShareAppMessage() {
    return {
      title: "AI 日报 - 每日 AI 资讯一览",
      path: "/pages/index/index",
    };
  },

  /** 分享到朋友圈 */
  onShareTimeline() {
    return {
      title: "AI 日报 - 每日 AI 资讯一览",
    };
  },
});
