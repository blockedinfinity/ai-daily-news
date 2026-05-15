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
      fail(err) {
        reject({ msg: "网络错误，请检查后端服务是否启动" });
      },
    });
  });
}

export const getNewsByDate = (date, page = 1) =>
  request("GET", `/news?date=${date}&page=${page}`);

export const getNewsDetail = (id) =>
  request("GET", `/news/${id}`);

export const getAvailableDates = () =>
  request("GET", "/dates");

export const getSummary = (date) =>
  request("GET", `/summary?date=${date}`);

export const generateSummary = (date) =>
  request("POST", `/summary/generate`, { date });
