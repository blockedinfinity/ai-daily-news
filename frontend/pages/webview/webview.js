Page({
  data: {
    url: "",
    loading: true,
    showFallback: false,
    canUseClipboard: true,
    loaded: false,
  },

  onLoad(options) {
    const url = decodeURIComponent(options.url || "");
    if (!url) {
      wx.showToast({ title: "链接无效", icon: "none" });
      setTimeout(() => wx.navigateBack(), 1000);
      return;
    }
    this.setData({ url });
    // 设置超时：如果 8 秒后 web-view 还没加载完成，显示兜底提示
    this._timer = setTimeout(() => {
      if (!this.data.loaded) {
        this.setData({ showFallback: true, loading: false });
      }
    }, 8000);
  },

  onUnload() {
    if (this._timer) clearTimeout(this._timer);
  },

  onWebviewLoad() {
    this.setData({ loaded: true, loading: false });
    if (this._timer) clearTimeout(this._timer);
  },

  onError() {
    this.setData({ showFallback: true, loading: false });
    if (this._timer) clearTimeout(this._timer);
  },

  onMessage(e) {
    // 接收 web-view postMessage
  },

  copyUrl() {
    const url = this.data.url;
    wx.setClipboardData({
      data: url,
      success() {
        wx.showToast({ title: "链接已复制", icon: "success" });
      },
    });
  },

  openExternal() {
    // 提示用户在浏览器中打开
    wx.setClipboardData({
      data: this.data.url,
      success() {
        wx.showModal({
          title: "链接已复制",
          content: "请在浏览器中粘贴并打开此链接",
          showCancel: false,
          confirmText: "知道了",
        });
      },
    });
  },
});
