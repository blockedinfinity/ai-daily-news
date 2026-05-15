Component({
  properties: {
    id: Number,
    title: String,
    source: String,
    summary: String,
    time: String,
  },

  methods: {
    onTap() {
      wx.navigateTo({
        url: `/pages/detail/detail?id=${this.properties.id}`,
      });
    },
  },
});
