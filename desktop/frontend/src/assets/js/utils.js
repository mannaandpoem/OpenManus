import { Greet } from '@/../wailsjs/go/main/App.js'
import axios from "axios"
import { ElMessage } from 'element-plus'

/** axios start */
// Create a new axios instance
const $axios = axios.create({
  baseURL: "api",
  timeout: 12000
})

// Request interceptors
$axios.interceptors.request.use(
  (config) => {
    config.headers["token"] = ''
    if (config.method == "post" || config.method == "put") {
      delNullProperty(config.data)
      fomateDateProperty(config.data)
    } else if (config.method == "get" || config.method == "delete") {
      delNullProperty(config.params)
      fomateDateProperty(config.params)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptors
$axios.interceptors.response.use(
  (response) => {
    //  console.log("response:", response)
    if (response.status == 200) {
      return response.data
    } else {
      pop("Exception occurred in response:" + response.status)
    }
  },
  (error) => {
    console.log("error:" + JSON.stringify(error))
    if (error.response == undefined || error.response == null) {
      pop("Unknown request error!")
      pop("Unknown request error!")
    } else if (error.response.status == 500) {
      pop("Unable to communicate with backend, please retry later!")
    } else {
      pop("Request error:" + error)
      pop("Request error:" + error)
    }
    return Promise.reject(error)
  }
)

function get(url, param) {
  return $axios.get(url, { params: param })
}

async function awaitGet(url, param) {
  return await $axios.get(url, { params: param })
}

function post(url, param) {
  return $axios.post(url, param)
}

async function awaitPost(url, param) {
  return await $axios.post(url, param)
}

function del(url, param) {
  return $axios.delete(url, { params: param })
}

async function awaitDel(url, param) {
  return await $axios.delete(url, { params: param })
}

/**
 * demo call Go interfaces
 */
function greet(name) {
  return Greet(name).then(resp => {
    console.log("greet resp:", resp)
    return resp
  })
}

/**
 * Check if object is null
 */
function isNull(obj) {
  return obj == undefined || obj == null
}

/**
 * Check if object is not null
 */
function notNull(obj) {
  return obj != undefined && obj != null
}

/**
 * Check if string is blank
 */
function isBlank(str) {
  return str == undefined || str == null || /^s*$/.test(str)
}

/**
 * Identify a non-empty string
 */
function notBlank(str) {
  return !isBlank(str)
}

/**
 * Check if array is empty
 */
function isEmpty(arr) {
  return arr == undefined || arr == null || (arr instanceof Array && arr.length == 0)
}

/**
 * Check if array is not empty
 */
function notEmpty(arr) {
  return arr != undefined && arr != null && arr instanceof Array && arr.length > 0
}

/**
 * Check if object is true
 */
function isTrue(obj) {
  return obj == true || obj == 'true'
}

/**
 * Check if object is false
 */
function isFalse(obj) {
  return !isTrue(obj)
}
/**
 * Get count of a specific character in a string
 * @param {string} str - String to search
 * @param {string} char - Character to find
 * @returns {number} - Occurrence count
 */
function getCharCount(str, char) {
  // g=match globally
  var regex = new RegExp(char, 'g')
  // Search for all occurrences of the character in the string
  var result = str.match(regex)
  var count = !result ? 0 : result.length
  return count
}

/**
 * Format date with specified pattern
 * @param {Date|string} date - Date object or date string
 * @param {string} format - Target format pattern; by default, `yyyy-MM-dd HH:mm:ss`
 * @returns {string} - Formatted date string
 */
function dateFormat(date, format) {
  if (date == undefined || date == null || date == '') {
    return date
  }
  if (format == undefined || format == null
    || format == '' || format == 0
    || format == "datetime" || format == 'date_time'
    || format == 'DATE_TIME' || format == 'DATETIME') {
    format = "yyyy-MM-dd HH:mm:ss"
  } else if (format == 'date' || format == 'DATE' || format == 1) {
    format = "yyyy-MM-dd"
  }
  date = new Date(date)
  const Y = date.getFullYear() + '',
    M = date.getMonth() + 1,
    D = date.getDate(),
    H = date.getHours(),
    m = date.getMinutes(),
    s = date.getSeconds()
  return format.replace(/YYYY|yyyy/g, Y)
    .replace(/YY|yy/g, Y.substring(2, 2))
    .replace(/MM/g, (M < 10 ? '0' : '') + M)
    .replace(/dd/g, (D < 10 ? '0' : '') + D)
    .replace(/HH|hh/g, (H < 10 ? '0' : '') + H)
    .replace(/mm/g, (m < 10 ? '0' : '') + m)
    .replace(/ss/g, (s < 10 ? '0' : '') + s)
}

/**
 * Recursively format Date properties in objects/arrays
 * @param {Object} obj - Target object to process
 */
function fomateDateProperty(obj) {
  for (let i in obj) {
    // Iterate through all properties of the object
    if (obj[i] == null) {
      continue
    } else if (obj[i] instanceof Date) {
      // Format as `yyyy-MM-dd HH:mm:ss`
      obj[i] = dateFormat(obj[i])
    } else if (obj[i].constructor === Object) {
      // Recursively format nested objects
      if (Object.keys(obj[i]).length > 0) {
        // Delete empty properties
        fomateDateProperty(obj[i])
      }
    } else if (obj[i].constructor === Array) {
      // Recursively clean nested arrays
      if (obj[i].length > 0) {
        for (let j = 0; j < obj[i].length; j++) {
          // Iterate through all array items
          fomateDateProperty(obj[i][j])
        }
      }
    }
  }
}

/**
 * Remove null/empty properties recursively
 * @param {Object} obj - Target object to clean
 */
function delNullProperty(obj) {
  for (let i in obj) {
    // Iterate through all properties of the object
    if (obj[i] === undefined || obj[i] === null || obj[i] === "") {
      // Delete general null/empty properties
      delete obj[i]
    } else if (obj[i].constructor === Object) {
      // Recursively clean nested objects
      if (Object.keys(obj[i]).length === 0) delete obj[i]
      // Delete empty properties
      delNullProperty(obj[i])
    } else if (obj[i].constructor === Array) {
      // Recursively clean arrays
      if (obj[i].length === 0) {
        // Delete empty arrays
        delete obj[i]
      } else {
        for (let index = 0; index < obj[i].length; index++) {
          // Iterate through all array items
          if (obj[i][index] === undefined || obj[i][index] === null || obj[i][index] === "" || JSON.stringify(obj[i][index]) === "{}") {
            obj[i].splice(index, 1)
            // Delete null/empty array items
            index--
            // Do decrement to avoid skipping next item (index is now pointing to the next item)
          }
          if (obj[i].constructor === Object) {
            // Recursively clean nested objects in array items
            delNullProperty(obj[i])
          }
        }
      }
    }
  }
}

/**
 * Display message notification
 * @param {string} msg - Message content
 * @param {string} type - Message type (success/warning/error/etc)
 */
function pop(msg, type) {
  ElMessage({ message: msg, type: type })
}

/**
 * Show default message when no data available
 * @param {*} data - Data to check
 */
function popNoData(data) {
  if (data == undefined || data == null || (data instanceof Array && data.length == 0)) {
    ElMessage("No data available!")
  }
}

/**
 * Get current datetime as formatted string
 * @returns {string} Current datetime in yyyy-MM-dd HH:mm format
 */
function nowDatetimeStr() {
  const date = new Date()
  const datetimeStr = `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
  return datetimeStr
}

/**
 * Pagination structure builder
 * @param {Object} source - Source pagination data
 * @param {Object} target - Target pagination object
 */
function buildPage(source, target) {
  target.pageNum = source.pageNum
  target.pageSize = source.pageSize
  target.total = source.total
  target.pages = source.pages
  copyArray(source.list, target.list)
}
/**
 * Clear array contents
 * @param {Array} arr - Array to clear
 */
function clearArray(arr) {
  if (arr == undefined || arr == null || arr.length == 0) {
    return
  }
  arr.splice(0, arr.length)
}

/**
 * Reset object properties to null
 * @param {Object} obj - Target object
 */
function clearProps(obj) {
  if (obj == undefined || obj == null) {
    return
  }
  for (let i in obj) {
    obj[i] = null
  }
}

/**
 * Copy properties between objects
 * @param {Object} source - Source object
 * @param {Object} target - Target object
 */
function copyProps(source, target = {}) {
  if (target == undefined || target == null) {
    target = {}
  }
  if (source == undefined || source == null) {
    source = new Object()
  }
  for (let i in target) {
    target[i] = (source[i] != undefined ? source[i] : null)
  }
}
/**
 * Clone array contents
 * @param {Array} source - Source array
 * @param {Array} target - Target array
 */
function copyArray(source, target) {
  if (target == undefined || target == null) {
    return
  }
  // Clear the array first
  if (target.length > 0) {
    target.splice(0, target.length)
    /* while (target.length > 0) {
        target.pop()
    } */
  }
  if (source == undefined || source == null) {
    return
  }
  for (let i of source) {
    target.push(i)
  }
}

/**
 * Find changed properties between objects
 * @param {Object} origin - Original object
 * @param {Object} target - Modified object
 * @returns {Object} Changed properties
 */
function dfProps(origin, target) {
  if (origin == undefined || origin == null || target == undefined || target == null) {
    return target
  }
  var dfObj = {}
  for (let i in target) {
    if (target[i] != null && target[i] != origin[i]) {
      dfObj[i] = target[i]
    }
  }
  return dfObj
}

/**
 * Check for property differences
 * @param {Object} origin - Original object
 * @param {Object} target - Modified object
 * @returns {boolean} True if differences exist
 */
function hasDfProps(origin, target) {
  const df = dfProps(origin, target)
  for (let i in df) {
    if (df[i] != null) {
      return true
    }
  }
  return false
}

/**
 * Check if all object properties are null
 * @param {Object} target - Object to check
 * @returns {boolean} True if all properties are null
 */
function isAllPropsNull(target) {
  if (target == undefined || target == null) {
    return true
  }
  for (let i in target) {
    if (target[i] != null) {
      return false
    }
  }
  return true
}

function colorByLabel(label) {
  if ('ADD' == label) {
    return 'bg-success'
  }
  if ('UPD' == label) {
    return 'bg-primary'
  }
  if ('DEL' == label) {
    return 'bg-danger'
  }
  if ('step' == label) {
    return 'bg-primary'
  }
  if ('log' == label) {
    return 'bg-success'
  }
  if ('tool' == label) {
    return 'bg-primary'
  }
  if ('think' == label) {
    return 'bg-danger'
  }
  if ('run' == label) {
    return 'bg-success'
  }
  if ('message' == label) {
    return 'bg-success'
  }
  if ('act' == label) {
    return 'bg-danger'
  }


}

function descByLabel(label) {
  if ('ADD' == label) {
    return 'Add'
  }
  if ('UPD' == label) {
    return 'Update'
  }
  if ('DEL' == label) {
    return 'Delete'
  }
  return label
}

/**
 * Retry calls
 * @param {Function} method - Method to call
 * @param {any} params - Method parameters that are passed to the method
 */
function retry(method) {
  const params = []
  for (var i = 1; i < arguments.length; i++) {
    params.push(arguments[i])
  }
  setTimeout(() => {
    method(params)
  }, 500)
}

/**
 * Resolve label from options
 * @param {string|number} keyOrVal - Key or value to resolve
 * @param {Array} opts - Options array
 * @returns {string} Resolved label if found, or original keyOrVal if not found
 */
function resolveLabelFromOpts(keyOrVal, opts) {
  if (isEmpty(opts)) {
    return keyOrVal
  }
  for (let opt of opts) {
    if (opt.key == keyOrVal || opt.value == keyOrVal) {
      return opt.label
    }
  }
  return keyOrVal
}

/**
 * Underscored string to camel case string
 * @param {String} underscore Underscored string
 * @returns Camel case string
 */
function underScoreToCamelCase(underscore) {
  if (isNull(underscore) || !underscore.includes('_')) {
    return underscore
  }
  const words = underscore.split('_')
  for (let i = 1; i < words.length; i++) {
    if (words[i] == "") {
      words[i] = ""
      continue
    }
    words[i] = words[i].substring(0, 1).toUpperCase() + words[i].substring(1, words[i].length)
  }
  return words.join("")
}

/**
 * Debounce a function call
 * @param {Function} func Function to debounce
 * @param {Number} delay Delay in milliseconds
 * @returns Debounced function
 */
function debounce(func, delay) {
  let timer
  return function () {
    const context = this
    const args = arguments

    clearTimeout(timer)
    timer = setTimeout(() => {
      func.apply(context, args)
    }, delay)
  }
}

/**
 * Convert string to lines
 */
function stringToLines(str) {
  if (str == undefined || str == null) {
    return []
  }
  return str.split('\n')
}

export default {
  /**
   * Synchronous GET HTTP request
   */
  get,

  /**
   * Asynchronous GET HTTP request (async/await)
   */
  awaitGet,

  /**
   * Synchronous POST HTTP request
   */
  post,

  /**
   * Asynchronous POST HTTP request (async/await)
   */
  awaitPost,

  /**
   * Synchronous DELETE HTTP request
   */
  del,

  /**
   * Asynchronous DELETE HTTP request (async/await)
   */
  awaitDel,

  /**
   * Checks if a value is null/undefined
   */
  isNull,

  /**
   * Verifies a value is not null/undefined
   */
  notNull,

  isBlank,

  notBlank,

  /**
   * Checks if an array is empty
   */
  isEmpty,

  /**
   * Verifies an array contains elements
   */
  notEmpty,

  isTrue,

  isFalse,

  getCharCount,

  /**
   * Displays a toast notification
   */
  pop,

  /**
   * Shows "No data" notification for empty datasets
   */
  popNoData,

  /**
   * Removes null/undefined properties from an object
   */
  delNullProperty,

  /**
   * Gets current datetime as formatted string (YYYY-MM-DD HH:mm:ss)
   */
  nowDatetimeStr,

  /**
   * Constructs pagination parameters
   */
  buildPage,

  /**
   * Clears all elements from an array
   */
  clearArray,

  /**
   * Resets object properties to null/undefined
   */
  clearProps,

  /**
   * Copies properties between objects
   */
  copyProps,

  /**
   * Creates a shallow array copy
   */
  copyArray,

  /**
   * Formats Date object to string (customizable format)
   */
  dateFormat,

  /**
   * Formats Date properties in objects to strings
   */
  fomateDateProperty,

  /**
   * Tracks changed properties between object states
   */
  dfProps,

  hasDfProps,

  isAllPropsNull,

  colorByLabel,

  descByLabel,

  /**
   * Retries failed operations with attempts
   */
  retry,

  resolveLabelFromOpts,

  underScoreToCamelCase,

  debounce,

  stringToLines,

}
