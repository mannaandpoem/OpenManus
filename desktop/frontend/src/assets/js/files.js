import { ReadAll, SaveFile } from '@/../wailsjs/go/main/App.js'
import utils from '@/assets/js/utils'

// Temporary cache for file information
function cache(fileObj, $event) {
  console.log('Caching fileObj start:', fileObj, $event.target, $event.dataTransfer)
  console.log('typeof fileObj:', Array.isArray(fileObj))
  // If fileObj is an array, create a new element and append to the array
  // event.target.files and event.dataTransfer.files are event properties in JavaScript related to file upload and drag-and-drop.
  // event.target.files: This property is used with HTML file input elements (<input type="file">),
  // When the user selects a file and triggers the change event, event.target.files can be used to get the list of files selected by the user.
  // event.dataTransfer.files: This property is used when the user drags and drops files onto an element,
  // event.dataTransfer.files can be used to get the list of dropped files.
  console.log('$event:', $event, $event.type)
  let files
  if ($event.type == 'change') {
    files = $event.target.files
  } else if ($event.type == 'drop') {
    files = $event.dataTransfer.files
  } else {
    console.error("Unrecognized event type")
    return
  }
  const file = files[0]
  console.log("Selected file:", file)
  const fileInfo = Array.isArray(fileObj) ? new Object() : fileObj
  fileInfo.file = file
  let URL = window.URL || window.webkitURL
  fileInfo.fileUrl = URL.createObjectURL(file)
  const fileType = file.type
  console.log("File type:", fileType, typeof (fileType))
  if (utils.notNull(fileType) && fileType.startsWith("image")) {
    fileInfo.imgUrl = fileInfo.fileUrl
  }
  fileInfo.fileName = file.name
  console.log('Caching fileObj completed:', fileInfo)
  if (Array.isArray(fileObj)) {
    // Append to the end of the array after successful operation
    fileObj.push(fileInfo)
  }
  if ($event.type == 'change') {
    // Solve the problem of selecting the same file not triggering the change event, clean up at the end
    $event.target.value = null
  }
}

// Upload file
async function upload(fileObj) {
  console.log("Preparing to upload file...", fileObj, fileObj.file, fileObj.fileId)
  // Current location handling
  if (utils.isNull(fileObj.file)) {
    if (utils.notNull(fileObj.fileId) && fileObj.remark != fileObj.remarkUpd) {
      let remark = null
      if (utils.notNull(fileObj.remarkUpd)) {
        remark = fileObj.remarkUpd
      }
      await updRemark(fileObj.fileId, remark)
    }
    return
  }
  console.log("Starting file upload...", fileObj, fileObj.file, fileObj.fileId)
  const url = '/common/file/upload'
  const formData = new FormData()
  formData.append('file', fileObj.file)
  if (utils.notNull(fileObj.remark)) {
    formData.append('remark', fileObj.remark)
  } else if (utils.notNull(fileObj.remarkUpd)) {
    formData.append('remark', fileObj.remarkUpd)
  }
  const data = await utils.awaitPost(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
  Object.assign(fileObj, data)
  console.log("File upload processed successfully", fileObj)
  return fileObj
}

// Update file remark
async function updRemark(fileId, remarkUpd) {
  const param = {
    fileId: fileId,
    remark: remarkUpd
  }
  await utils.awaitPost('/common/file/updRemark', param)
  console.log("File remark updated successfully")
}

// Batch upload files
async function uploads(fileObjs) {
  if (utils.isEmpty(fileObjs)) {
    return
  }
  for (let index in fileObjs) {
    console.log('Processing file object:', fileObjs, index, fileObjs.length, fileObjs[index])
    await upload(fileObjs[index])
    console.log("uploads index:", index, "File upload completed", fileObjs[index])
  }
}

// Handle file upload (onChange event)
function upOnChg(fileObj, $event) {
  const file = $event.target.files[0] || $event.dataTransfer.files[0]
  // Current location
  let URL = window.URL || window.webkitURL
  // Convert to blob URL
  fileObj.fileUrl = URL.createObjectURL(file)
  const url = '/common/file/upload'
  const formData = new FormData()
  formData.append('file', file)
  formData.append('remark', fileObj.remark)
  utils.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }).then((data) => {
    console.log("File upload result:", data)
    Object.assign(fileObj, data)
    fileObj.remarkUpd = data.remark
  })
}

// Add to component list
function add(fileList) {
  const comp = {
    index: fileList.length,
    file: null,
    fileId: null,
    fileName: null,
    fileUrl: null,
    imgUrl: null,
    remark: null
  }
  fileList.push(comp)
}

// Remove component from list
function del(fileObj, index) {
  console.log("Deleting file object:", fileObj, index)
  if (Array.isArray(fileObj)) {
    fileObj.splice(index, 1)
  } else {
    utils.clearProps(fileObj)
  }
}

// Convert between Java and JS file objects
function trans(javaFile, jsFile) {
  if (jsFile == undefined || jsFile == null) {
    return
  }
  // Clear array if present
  if (jsFile instanceof Array) {
    jsFile.splice(0, jsFile.length)
  } else {
    utils.clearProps(jsFile)
  }

  if (javaFile == undefined || javaFile == null) {
    return
  }
  // Handle array type
  if (jsFile instanceof Array) {
    for (let java of javaFile) {
      const js = {}
      java.remarkUpd = java.remark
      Object.assign(js, java)
      jsFile.push(js)
    }
  } else {
    // Handle object type
    console.log("Object type conversion", jsFile instanceof Array)
    javaFile.remarkUpd = javaFile.remark
    Object.assign(jsFile, javaFile)
  }
}

// Collect file IDs from components
function fileIds(fileList) {
  return fileList.map(comp => comp.fileId).join(',')
}

// Read file contents
function readAll(filePath) {
  return ReadAll(filePath)
}

// Await Read file contents
async function awaitReadAll(filePath) {
  return await ReadAll(filePath)
}

// Save file
function saveFile(filePath, content) {
  return SaveFile(filePath, content)
}

/**
 * Reads a TOML node info to a json object
 */
async function readTomlNode(filePath, nodeName) {
  const fileContent = await readAll(filePath)
  // console.log("Read Toml file, filePath:", filePath, ", fileContent:", fileContent)
  if (utils.isBlank(fileContent)) {
    utils.pop(t('readTomlFailed'))
    return
  }
  const lines = utils.stringToLines(fileContent)

  // Read Node
  const nodeStart = lines.findIndex((line) => {
    return line.includes("[" + nodeName + "]")
  })
  const node = {}
  for (let i = nodeStart + 1; i < lines.length; i++) {
    // console.log("line: ", lines[i])
    // Determine whether the next configuration module has been reached.
    if (lines[i].startsWith("[")) {
      break
    }
    // 读取配置
    const line = lines[i]
    if (line.startsWith("#")) {
      continue
    }
    const lineArr = line.split("=")
    if (lineArr.length == 0) {
      continue
    }
    const key = lineArr[0].trim()
    let value = ""
    if (lineArr.length == 2) {
      value = lineArr[1].trim()
    }
    node[key] = value
  }
  console.log("Read node from toml file, result: ", node)
  return node
}

/**
 * Save a toml node
 */
async function saveTomlNode(filePath, nodeName, newNodeJson) {
  const fileContent = await readAll(filePath)
  // console.log("Read Toml file, filePath:", filePath, ", fileContent:", fileContent)
  if (utils.isBlank(fileContent)) {
    utils.pop(t('readTomlFailed'))
    return
  }
  const lines = utils.stringToLines(fileContent)

  // Read Node
  const nodeStart = lines.findIndex((line) => {
    return line.includes("[" + nodeName + "]")
  })

  for (let i = nodeStart + 1; i < lines.length; i++) {
    // console.log("line: ", lines[i])
    // Determine whether the next configuration module has been reached.
    if (lines[i].startsWith("[")) {
      break
    }
    // 读取配置
    const line = lines[i]
    if (line.startsWith("#")) {
      continue
    }
    const lineArr = line.split("=")
    if (lineArr.length == 0) {
      continue
    }
    const key = lineArr[0].trim()
    let value = newNodeJson[key]
    if (utils.isNull(value)) {
      continue
    }
    value = value.trim()
    lines[i] = key + " = " + value
  }
  console.log("Save node from toml file, new lines: ", lines)
  const newContent = lines.join("\n")
  await saveFile(filePath, newContent)
}

export default {
  // Cache on onChange
  cache,
  // Upload file
  upload,
  // Upload files
  uploads,
  // Upload file
  upOnChg,
  // Upload on onChange
  upOnChg,
  // Add to component list
  add,
  // Delete component from component list
  del,
  // Convert between Java object and js object
  trans,
  // Collect fileId from Comps
  fileIds,
  // Read file
  readAll,
  // Read toml node
  readTomlNode,
  // Save toml node
  saveTomlNode,
}
