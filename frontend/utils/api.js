const app = getApp();

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + path,
      method,
      data,
      header: { "Content-Type": "application/json" },
      success(res) {
        if (res.data.code === 0) {
          resolve(res.data.data);
        } else {
          reject({ msg: res.data.message || "请求失败" });
        }
      },
      fail() {
        reject({ msg: "网络错误，请检查后端服务是否启动" });
      },
    });
  });
}

/** 获取今日新闻 */
export const getTodayNews = () => request("GET", "/news/today");

/** 按日期获取新闻（带分页） */
export const getNewsByDate = (date, page = 1) =>
  request("GET", `/news?date=${date}&page=${page}`);

/** 获取单条新闻详情 */
export const getNewsDetail = (id) => request("GET", `/news/${id}`);

/** 获取所有有新闻的日期列表 */
export const getAvailableDates = () => request("GET", "/dates");

/** 获取某日 AI 摘要 */
export const getSummary = (date) => request("GET", `/summary?date=${date}`);

/** 触发生成某日 AI 摘要 */
export const generateSummary = (date) =>
  request("POST", "/summary/generate", { date });

/** 获取有 AI 总结的日期列表 */
export const getSummaryDates = () => request("GET", "/summary-dates");
