import { getProjectDates, getProject } from "../../utils/api";
import { formatLabel } from "../../utils/util";

Page({
  data: {
    dates: [],
    currentDate: "",
    currentLabel: "今天",
    showDates: false,
    project: null,
    loading: true,
    noProject: false,
  },

  onLoad() {
    this.loadDates();
  },

  toggleDates() {
    this.setData({ showDates: !this.data.showDates });
  },

  async loadDates() {
    try {
      const today = getApp().globalData.today;

      const projectDates = await getProjectDates();
      const formatted = projectDates.map((d) => ({
        ...d,
        label: formatLabel(d.date, today),
      }));

      // 确保今天始终在列表中
      const hasToday = formatted.some((d) => d.date === today);
      if (!hasToday) {
        formatted.unshift({ date: today, label: "今天" });
      }

      const currentDate = today;
      const current = formatted.find((d) => d.date === today);

      this.setData({
        dates: formatted,
        currentDate,
        currentLabel: current ? current.label : "今天",
      });

      this.loadProject(currentDate);
    } catch (e) {
      this.setData({ loading: false });
    }
  },

  async loadProject(date) {
    if (!date) return;
    this.setData({ loading: true, project: null, noProject: false });

    try {
      const result = await getProject(date);
      this.setData({ project: result, loading: false });
    } catch (e) {
      if (e.msg && (e.msg.includes("暂无") || e.msg.includes("404"))) {
        this.setData({ loading: false, noProject: true });
      } else {
        this.setData({ loading: false, noProject: true });
      }
    }
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
      showDates: false,
    });
    this.loadProject(date);
  },

  /** 分享给微信好友 */
  onShareAppMessage() {
    const date = this.data.currentDate || "";
    return {
      title: "AI 精品项目推荐 - 每日精选",
      path: `/pages/summary/summary?date=${date}`,
    };
  },

  /** 分享到朋友圈 */
  onShareTimeline() {
    return {
      title: "AI 精品项目推荐 - 每日精选",
    };
  },
});
