App({
  globalData: {
    baseUrl: "https://windflycool.pythonanywhere.com/api",
    today: "",
  },

  onLaunch() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    this.globalData.today = `${y}-${m}-${d}`;
  },
});
