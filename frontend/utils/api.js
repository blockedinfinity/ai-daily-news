const app = getApp();

/** 缓存存储 */
const _cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 分钟 TTL

/**
 * 生成缓存 key
 */
function cacheKey(method, path, data) {
  return `${method}:${path}:${JSON.stringify(data || {})}`;
}

/**
 * 带缓存的请求封装
 * - 缓存命中且未过期：直接返回缓存数据
 * - 缓存过期（stale）：先返回旧数据，再后台刷新
 * - 无缓存：正常发起请求
 */
function request(method, path, data, { skipCache = false } = {}) {
  const key = cacheKey(method, path, data);
  const now = Date.now();
  const cached = _cache.get(key);

  // GET 请求启用缓存，非 GET 或 skipCache=true 时跳过缓存
  const useCache = method === "GET" && !skipCache;

  return new Promise((resolve, reject) => {
    // 命中缓存且未过期 → 直接返回
    if (useCache && cached && now - cached.ts < CACHE_TTL) {
      return resolve(cached.data);
    }

    // 命中缓存但已过期 → stale-while-revalidate：先返回旧数据，再后台刷新
    if (useCache && cached) {
      resolve(cached.data);
      // 后台刷新，不阻塞当前 promise
      doRequest(method, path, data, key, useCache).catch(() => {
        // 后台刷新失败，忽略（继续使用旧数据）
      });
      return;
    }

    // 无缓存 → 正常请求
    doRequest(method, path, data, key, useCache).then(resolve).catch(reject);
  });
}

/**
 * 实际发起 wx.request
 */
function doRequest(method, path, data, key, useCache) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + path,
      method,
      data,
      header: { "Content-Type": "application/json" },
      timeout: 15000, // 15 秒超时
      success(res) {
        if (res.data.code === 0) {
          const result = res.data.data;
          if (useCache) {
            _cache.set(key, { data: result, ts: Date.now() });
          }
          resolve(result);
        } else {
          reject({ msg: res.data.message || "请求失败" });
        }
      },
      fail(err) {
        reject({ msg: "网络错误，请检查后端服务是否启动", detail: err });
      },
    });
  });
}

/** 清除所有缓存 */
export const clearCache = () => _cache.clear();

/** 清除指定路径的缓存 */
export const clearCacheByPrefix = (prefix) => {
  for (const key of _cache.keys()) {
    if (key.startsWith(prefix)) _cache.delete(key);
  }
};

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

/** 触发生成某日 AI 摘要（POST，跳过缓存） */
export const generateSummary = (date) =>
  request("POST", "/summary/generate", { date }, { skipCache: true });

/** 获取有 AI 总结的日期列表 */
export const getSummaryDates = () => request("GET", "/summary-dates");

/** 获取指定日期的精品项目 */
export const getProject = (date) => request("GET", `/project?date=${date}`);

/** 获取有精品项目的日期列表 */
export const getProjectDates = () => request("GET", "/project-dates");
