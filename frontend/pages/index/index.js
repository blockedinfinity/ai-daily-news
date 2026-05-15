const app = getApp();

Page({
  data: {
    newsList: [],
    loading: true,
    error: "",
  },

  onLoad() {
    this.loadNews();
  },

  onPullDownRefresh() {
    this.loadNews().then(() => wx.stopPullDownRefresh());
  },

  loadNews() {
    this.setData({ loading: true, error: "" });
    const that = this;

    return new Promise((resolve) => {
      wx.request({
        url: app.globalData.baseUrl + "/news/today",
        method: "GET",
        header: { "Content-Type": "application/json" },
        success(res) {
          if (res.data.code === 0) {
            that.setData({ newsList: res.data.data || [], loading: false });
          } else {
            that.setData({ error: res.data.message || "请求失败", loading: false });
          }
        },
        fail() {
          that.setData({ error: "网络错误，请检查后端服务", loading: false });
        },
        complete() {
          resolve();
        },
      });
    });
  },

  goDetail(e) {
    const { id, title, summary, url } = e.currentTarget.dataset;
    const params = `id=${id}&title=${encodeURIComponent(title || "")}&summary=${encodeURIComponent(summary || "")}&url=${encodeURIComponent(url || "")}`;
    wx.navigateTo({ url: `/pages/detail/detail?${params}` });
  },
});
