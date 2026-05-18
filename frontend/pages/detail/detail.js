import { getNewsDetail } from "../../utils/api";

const app = getApp();

Page({
  data: {
    news: null,
    loading: true,
    error: "",
  },

  onLoad(options) {
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

  async loadDetail(id) {
    this.setData({ loading: true, error: "" });
    try {
      const data = await getNewsDetail(id);
      // 处理摘要：按行分割，去除空行
      const lines = (data.summary || "")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      data.summaryLines = lines;
      this.setData({ news: data, loading: false });
    } catch {
      this.setData({ error: "加载失败，请重试", loading: false });
    }
  },

  openUrl() {
    const url = this.data.news?.url;
    if (!url) return;
    wx.navigateTo({
      url: "/pages/webview/webview?url=" + encodeURIComponent(url),
    });
  },

  copyUrl() {
    const url = this.data.news?.url;
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success() {
        wx.showToast({ title: "链接已复制", icon: "success" });
      },
    });
  },

  previewImage(e) {
    const src = e.currentTarget.dataset.src;
    if (!src) return;
    wx.previewImage({
      current: src,
      urls: [src],
    });
  },
});
