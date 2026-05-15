const app = getApp();

Page({
  data: {
    news: null,
    loading: true,
    error: "",
  },

  onLoad(options) {
    // 支持两种方式：
    // 1. 只传 id → 从 API 获取完整数据
    // 2. 直接传 title / summary / url 等字段 → 直接展示（免请求）
    if (options.id) {
      this.loadDetail(options.id);
    } else if (options.title) {
      this.setData({
        news: {
          id: options.id || 0,
          title: decodeURIComponent(options.title),
          summary: decodeURIComponent(options.summary || ""),
          url: decodeURIComponent(options.url || ""),
          time: options.time || "",
        },
        loading: false,
      });
    } else {
      this.setData({ loading: false, error: "缺少参数" });
    }
  },

  loadDetail(id) {
    this.setData({ loading: true, error: "" });
    const that = this;

    wx.request({
      url: app.globalData.baseUrl + "/news/" + id,
      method: "GET",
      header: { "Content-Type": "application/json" },
      success(res) {
        if (res.data.code === 0) {
          that.setData({ news: res.data.data, loading: false });
        } else {
          that.setData({ error: res.data.message || "请求失败", loading: false });
        }
      },
      fail() {
        that.setData({ error: "网络错误", loading: false });
      },
    });
  },

  openUrl() {
    const url = this.data.news?.url;
    if (!url) return;
    wx.navigateTo({ url: "/pages/webview/webview?url=" + encodeURIComponent(url) });
  },
});
