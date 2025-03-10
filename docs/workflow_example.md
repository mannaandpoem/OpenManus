# OpenManus Agent执行流程示例

## 场景：创建一个简单的天气查询应用

### 执行流程概述

1. 接收用户查询天气的请求
2. 使用GoogleSearch获取天气信息
3. 使用PythonExecute处理数据
4. 使用FileSaver保存结果
5. 使用BrowserUseTool展示结果
6. 使用Terminate结束任务

### 详细执行步骤

```
步骤1: 思考(Think)
- 分析用户请求："查询北京今天的天气"
- 决定使用GoogleSearch工具获取信息

步骤1: 行动(Act)
- 调用: GoogleSearch(query="北京今天天气预报", num_results=3)
- 结果: 获取到天气相关网页和摘要信息

步骤2: 思考(Think)
- 分析搜索结果，提取天气信息
- 决定使用PythonExecute处理数据

步骤2: 行动(Act)
- 调用: PythonExecute
  代码:
  ```python
  # 从搜索结果中提取天气信息
  weather_data = {
      "城市": "北京",
      "日期": "2023-11-15",
      "天气": "晴",
      "温度": "12°C ~ -2°C",
      "风向": "西北风",
      "风力": "3-4级",
      "空气质量": "良"
  }
  
  # 生成天气报告
  report = f"""
  {weather_data['城市']}天气报告
  日期: {weather_data['日期']}
  天气状况: {weather_data['天气']}
  温度范围: {weather_data['温度']}
  风向: {weather_data['风向']}
  风力: {weather_data['风力']}
  空气质量: {weather_data['空气质量']}
  """
  
  print(report)
  ```
- 结果: 生成格式化的天气报告

步骤3: 思考(Think)
- 决定将天气报告保存为文件
- 选择使用FileSaver工具

步骤3: 行动(Act)
- 调用: FileSaver(content=report, file_path="beijing_weather.txt")
- 结果: 天气报告保存到文件

步骤4: 思考(Think)
- 决定创建一个可视化的HTML天气报告
- 选择使用PythonExecute生成HTML

步骤4: 行动(Act)
- 调用: PythonExecute
  代码:
  ```python
  # 生成HTML天气报告
  html_content = f"""
  <!DOCTYPE html>
  <html>
  <head>
      <title>{weather_data['城市']}天气报告</title>
      <style>
          body {{ font-family: Arial; margin: 40px; background-color: #f0f8ff; }}
          .weather-card {{ 
              padding: 20px; 
              border-radius: 10px; 
              background-color: white;
              box-shadow: 0 4px 8px rgba(0,0,0,0.1);
              max-width: 500px;
              margin: 0 auto;
          }}
          .city {{ font-size: 24px; color: #4682b4; }}
          .date {{ color: #708090; margin-bottom: 15px; }}
          .temp {{ font-size: 20px; margin: 10px 0; }}
          .condition {{ display: flex; align-items: center; margin: 10px 0; }}
          .quality {{ 
              display: inline-block;
              padding: 5px 10px;
              border-radius: 15px;
              background-color: #98fb98;
              color: #006400;
          }}
      </style>
  </head>
  <body>
      <div class="weather-card">
          <div class="city">{weather_data['城市']}</div>
          <div class="date">{weather_data['日期']}</div>
          <div class="temp">{weather_data['温度']}</div>
          <div class="condition">
              <span>天气: {weather_data['天气']}</span>
          </div>
          <div>风向: {weather_data['风向']} {weather_data['风力']}</div>
          <div>空气质量: <span class="quality">{weather_data['空气质量']}</span></div>
      </div>
  </body>
  </html>
  """
  
  print("HTML天气报告已生成")
  ```
- 结果: 生成HTML天气报告

步骤5: 思考(Think)
- 决定保存HTML报告并在浏览器中显示
- 选择使用FileSaver和BrowserUseTool

步骤5: 行动(Act)
- 调用: FileSaver(content=html_content, file_path="beijing_weather.html")
- 结果: HTML报告保存到文件

步骤6: 思考(Think)
- 决定在浏览器中打开HTML报告
- 选择使用BrowserUseTool

步骤6: 行动(Act)
- 调用: BrowserUseTool(action="navigate", url="file:///完整路径/beijing_weather.html")
- 结果: 浏览器打开HTML天气报告

步骤7: 思考(Think)
- 分析任务完成情况，确认所有要求已满足
- 决定结束任务

步骤7: 行动(Act)
- 调用: Terminate(status="success")
- 结果: 任务成功完成
```

### 执行流程图

```
初始化
  ↓
接收用户请求
  ↓
思考 → 行动(GoogleSearch) → 更新记忆
  ↓
思考 → 行动(PythonExecute) → 更新记忆
  ↓
思考 → 行动(FileSaver) → 更新记忆
  ↓
思考 → 行动(PythonExecute) → 更新记忆
  ↓
思考 → 行动(FileSaver) → 更新记忆
  ↓
思考 → 行动(BrowserUseTool) → 更新记忆
  ↓
思考 → 行动(Terminate) → 任务完成
```

### 关键特点

1. **循环决策过程**：每一步都包含思考(Think)和行动(Act)两个阶段
2. **工具选择**：根据当前任务需求选择最合适的工具
3. **记忆更新**：每次行动后更新记忆，为下一步决策提供依据
4. **终止条件**：任务完成后主动终止

这个示例展示了OpenManus如何通过ReAct范式处理天气查询任务，从信息获取到结果展示的完整流程。