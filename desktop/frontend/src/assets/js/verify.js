import utils from '@/assets/js/utils'

/** Regex for English letters, numbers, and underscores */
const codeReg = /^[A-Za-z0-9_\-\.]+$/

/** Regex for mobile phone number in China (Mainland) */
const mobileReg = /^1[3456789]\d{9}$/

/** Regex for ID card number in China (Mainland) */
const idNoReg = /^(^[1-9]\d{7}((0\d)|(1[0-2]))(([0|1|2]\d)|3[0-1])\d{3}$)|(^[1-9]\d{5}[1-9]\d{3}((0\d)|(1[0-2]))(([0|1|2]\d)|3[0-1])((\d{4})|\d{3}[Xx])$)$/

/** Regex for email */
const emailReg = /^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$/

const commonValidator = (rule, value, callback) => {
  if (utils.isNull(value)) {
    callback()
  } else {
    callback()
  }
}

const notBlankValidator = (rule, value, callback) => {
  if (utils.isBlank(value)) {
    callback(new Error('Input cannot be blank'))
  } else {
    callback()
  }
}

const nameValidator = (rule, value, callback) => {
  if (utils.isBlank(value)) {
    callback()
  } else if (value.length > 50) {
    callback(new Error('Name too long (max 50 characters)'))
  } else {
    callback()
  }
}

const mobileValidator = (rule, value, callback) => {
  if (utils.isNull(value)) {
    callback()
  } else if (!mobileReg.test(value)) {
    callback(new Error('Invalid mobile number'))
  } else {
    callback()
  }
}

const idNoValidator = (rule, value, callback) => {
  if (utils.isNull(value)) {
    callback()
  } else if (!idNoReg.test(value)) {
    callback(new Error('Invalid ID card number'))
  } else {
    callback()
  }
}

const emailValidator = (rule, value, callback) => {
  if (utils.isNull(value)) {
    callback()
  } else if (!emailReg.test(value)) {
    callback(new Error('Invalid email address'))
  } else {
    callback()
  }
}

const codeValidator = (rule, value, callback) => {
  if (utils.isBlank(value)) {
    callback()
  } else if (!codeReg.test(value)) {
    callback(new Error('Invalid code format'))
    callback(new Error('Invalid code format'))
  } else {
    callback()
  }
}

const intValidator = (rule, value, callback) => {
  if (utils.isBlank(value)) {
    callback()
  } else if (!Number.isInteger(value)) {
    callback(new Error('Input must be an integer'))
  } else {
    callback()
  }
}

function validator() {
  // console.log("arguments:", arguments)
  if (arguments.length <= 1) {
    const type = arguments[0]
    // Default validation logic, no special characters
    if (utils.isBlank(type)) {
      return commonValidator
    } else if (type == 'notBlank') {
      return notBlankValidator
    } else if (type == 'name') {
      return nameValidator
    } else if (type == 'mobile') {
      return mobileValidator
    } else if (type == 'idNo') {
      return idNoValidator
    } else if (type == 'email') {
      return emailValidator
    } else if (type == 'code') {
      return codeValidator
    } else if (type == 'int') {
      return intValidator
    } else {
      return commonValidator
    }
  }
  // Complex validators
  const complexValidator = (rule, value, callback) => {
    for (let i = 0; i < arguments.length; i++) {
      const typeStr = arguments[i]
      if (typeStr == 'notBlank' && utils.isBlank(value)) {
        callback(new Error('Input cannot be blank'))
        break
      } else if (typeStr == 'code' && !codeReg.test(value)) {
        callback(new Error('Invalid code format'))
        break
      } else if (typeStr == 'int' && Number.isInteger(value)) {
        callback(new Error('Please enter an integer'))
        break
      }
    }
    // Ensure callback is called at least once
    callback()
  }
  return complexValidator
}

export default {

  username: (username) => {
    if (typeof (username) == "undefined" || username == null) {
      return "Username cannot be blank"
    }
    username = username.trim()
    if (username.length < 4) {
      return "Username must be at least 4 characters long"
    }
    if (username.length > 20) {
      return "Username must be at most 20 characters long"
    }
    const reg = /^[A-Za-z0-9]+$/
    if (!reg.test(username)) {
      return "Username must be letters and numbers only"
    }
    return null
  },

  password: (password) => {
    if (typeof (password) == "undefined" || password == null) {
      return "Password cannot be blank"
    }
    password = password.trim()
    if (password.length < 4) {
      return "Password must be at least 4 characters long"
    }
    if (password.length > 20) {
      return "Password must be at most 20 characters long"
    }
    const reg = /^[A-Za-z0-9\.\-\_\+]+$/
    if (!reg.test(password)) {
      return "Password must be letters, numbers, and special characters (.-_+) only"
    }
    return null
  },

  email: (email) => {
    if (typeof (email) == "undefined" || email == null) {
      return "Email cannot be blank"
    }
    const reg = /^[A-Za-z0-9._%-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,4}$/
    if (!reg.test(email)) {
      return "Invalid email address"
    }
    return null
  },

  validCode: (validCode) => {
    if (typeof (validCode) == "undefined" || validCode == null) {
      return "Verification code cannot be blank"
    }
    validCode = validCode.trim()
    if (validCode.length != 6) {
      return "Verification code must be 6 characters long"
    }
    const reg = /^[A-Za-z0-9]{6}$/
    if (!reg.test(validCode)) {
      return "Invalid verification code format"
    }
    return null
  },

  validator,


}
