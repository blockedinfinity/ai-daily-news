Page({
  data: {
    url: "",
  },

  onLoad(options) {
    const url = decodeURIComponent(options.url || "");
    if (url) {
      this.setData({ url });
    } else {
      wx.showToast({ title: "链接无效", icon: "none" });
      setTimeout(() => wx.navigateBack(), 1000);
    }
  },
});
