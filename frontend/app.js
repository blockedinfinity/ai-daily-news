App({
  globalData: {
    baseUrl: "http://localhost:5000/api",
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
