/**
 * uni.request 封装（小程序无 axios）。
 * 统一 baseURL / 超时 / 错误处理，返回业务 data。
 */

// 后端 API 根。
// - 开发：局域网 192 IP（manifest 已关 urlCheck，真机/模拟器可访问）
// - 发布/联调：必须为 https 已备案域名，且在「微信公众平台 → 开发管理 → 服务器域名」把
//   https://taoism.test.doouu.cc 加入 request 合法域名、uploadFile 合法域名（舌诊/化验单上传用）。
// 用 DEV 自动切换：本地预览用局域网，打包发布用线上域名。
export const API_BASE = import.meta.env.DEV
  ? "http://192.168.50.145:8000/api"
  : "https://taoism.test.doouu.cc/api";
// 站点根（/reports 等非 /api 资源）
export const API_ORIGIN = API_BASE.replace(/\/api\/?$/, "");

type Method = "GET" | "POST" | "PUT" | "DELETE";

interface RequestOptions {
  url: string;
  method?: Method;
  data?: Record<string, any>;
  header?: Record<string, string>;
  timeout?: number;
  silent?: boolean; // 静默：非 2xx / 失败不弹 toast，由调用方自行处理（如轮询）
}

// 微信 wx.request 会把 undefined/null 序列化成字符串 "undefined"/"null"
// （如 ?category=undefined），导致后端按假值过滤。发请求前剔除。
function compact(data?: Record<string, any>) {
  if (!data) return data;
  const out: Record<string, any> = {};
  for (const k of Object.keys(data)) {
    if (data[k] !== undefined && data[k] !== null) out[k] = data[k];
  }
  return out;
}

export function request<T = any>(opts: RequestOptions): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: API_BASE + opts.url,
      method: opts.method || "GET",
      data: compact(opts.data),
      timeout: opts.timeout ?? 60000,
      header: {
        "Content-Type": "application/json",
        ...(opts.header || {}),
      },
      success: (res) => {
        const status = res.statusCode;
        if (status >= 200 && status < 300) {
          resolve(res.data as T);
        } else {
          if (!opts.silent) uni.showToast({ title: "服务繁忙，请稍后重试", icon: "none" });
          reject(res);
        }
      },
      fail: (err) => {
        if (!opts.silent) uni.showToast({ title: "网络异常，请稍后重试", icon: "none" });
        reject(err);
      },
    });
  });
}

export const http = {
  get: <T = any>(url: string, data?: Record<string, any>) =>
    request<T>({ url, method: "GET", data }),
  /** 静默 GET：失败不弹 toast，留给调用方（轮询场景必用） */
  getSilent: <T = any>(url: string, data?: Record<string, any>) =>
    request<T>({ url, method: "GET", data, silent: true }),
  post: <T = any>(url: string, data?: Record<string, any>) =>
    request<T>({ url, method: "POST", data }),
  postWithHeaders: <T = any>(
    url: string,
    data?: Record<string, any>,
    header?: Record<string, string>,
    timeout = 60000
  ) => request<T>({ url, method: "POST", data, header, timeout }),
  deleteWithHeaders: <T = any>(url: string, header?: Record<string, string>) =>
    request<T>({ url, method: "DELETE", header }),
  getWithHeaders: <T = any>(
    url: string,
    header?: Record<string, string>,
    silent = false
  ) => request<T>({ url, method: "GET", header, silent }),
};

/** multipart 文件上传（uni.uploadFile，后端返回 JSON）。后端字段名固定为 file。
 *  注意：与 request() 不同，本函数不弹任何 toast —— 非 2xx 时把整个 res
 *  （含 statusCode/data）reject 给调用方，由调用方决定交互（重拍 vs 降级）。 */
export function upload<T = any>(
  url: string,
  filePath: string,
  formData?: Record<string, any>,
  timeout = 60000
): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: API_BASE + url,
      filePath,
      name: "file",
      formData: compact(formData),
      timeout,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            // uploadFile 的 res.data 是字符串，需手动 parse
            resolve(JSON.parse(res.data) as T);
          } catch {
            reject(new Error("响应解析失败"));
          }
        } else {
          reject(res); // res.statusCode 供调用方判别（如 400=后端拒收）
        }
      },
      fail: reject,
    });
  });
}

/** 带匿名问诊令牌的 V2 附件上传。 */
export function uploadAuthorized<T = any>(
  url: string,
  filePath: string,
  header: Record<string, string>,
  timeout = 180000
): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: API_BASE + url,
      filePath,
      name: "file",
      header,
      timeout,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          Promise.resolve(res.data).then(JSON.parse).then(resolve, reject);
        } else {
          reject(res);
        }
      },
      fail: reject,
    });
  });
}
