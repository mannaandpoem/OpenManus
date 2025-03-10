import asyncio
import time

from app.agent.manus import Manus
from app.logger import logger
from app.llm import LLM
from app.config import Config


async def test_api_connection():
    """
    测试与LLM API的连接情况
    
    Returns:
        bool: 连接测试是否成功
        float: 响应时间（秒）
    """
    logger.info("正在测试与LLM API的连接...")
    start_time = time.time()
    try:
        # 创建一个短的测试请求
        llm = LLM()
        test_msg = [{"role": "user", "content": "Hello"}]
        # 设置较短的超时时间用于测试
        response = await llm.ask(test_msg, stream=False, temperature=0)
        elapsed = time.time() - start_time
        logger.info(f"API连接测试成功！响应时间: {elapsed:.2f} 秒")
        return True, elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"API连接测试失败: {e}")
        return False, elapsed


async def read_multiline_input():
    """
    读取用户的多行输入，直到用户输入'---'结束或'exit'退出

    Returns:
        str: 用户输入的多行文本，如果用户输入'exit'则返回'exit'
    """
    lines = []
    logger.info("请输入您的指令 (可以输入多行，输入'---'结束，或输入'exit'退出):")
    print("> ", end="", flush=True)  # 显示提示符
    
    while True:
        try:
            line = input()
            if line.strip() == "---":
                break
            if line.strip().lower() == "exit":
                return "exit"
            lines.append(line)
            print("> ", end="", flush=True)  # 继续显示提示符
        except EOFError:  # 处理 Ctrl+D
            logger.info("检测到EOF，结束输入")
            break
    
    return "\n".join(lines)


async def main():
    # 显示欢迎信息
    print("\n====================================================")
    print("欢迎使用 OpenManus AI 助手!")
    print("====================================================\n")
    
    # 测试API连接
    print("程序启动前正在测试API连接状态...\n")
    success, response_time = await test_api_connection()
    
    if not success:
        print("\n⚠️ API连接测试失败! 程序可能无法正常工作。")
        print("您可以选择:")
        print("1. 检查网络连接")
        print("2. 验证API密钥是否正确")
        print("3. LLM API服务可能暂时不可用")
        print("\n如果您仍然想继续，可以输入指令，但可能会遇到超时错误。")
        print("输入'exit'可以退出程序。\n")
    else:
        if response_time > 5:
            print(f"\n⚠️ API连接测试成功，但响应较慢 ({response_time:.2f}秒)。")
            print("您可能会在使用过程中遇到超时问题。\n")
        else:
            print(f"\n✅ API连接测试成功! 响应时间: {response_time:.2f}秒\n")
    
    # 显示使用说明
    print("本程序支持多行输入，请按以下方式使用：")
    print("1. 输入您的问题或指令 (可以跨多行)")
    print("2. 输入 '---' 结束输入并提交处理")
    print("3. 输入 'exit' 或按 Ctrl+C 退出程序")
    print("====================================================\n")
    
    agent = Manus()
    
    while True:
        try:
            prompt = await read_multiline_input()
            if prompt.lower() == "exit":
                logger.info("Goodbye!")
                break
            
            if not prompt.strip():
                logger.warning("输入为空，请重新输入")
                continue
                
            logger.warning("正在处理您的请求...")
            try:
                await asyncio.wait_for(agent.run(prompt), timeout=120)  # 设置整体超时为120秒
            except asyncio.TimeoutError:
                print("\n⚠️ 请求处理超时! 这可能是由于:")
                print("- 网络延迟过高")
                print("- 请求复杂度过高")
                print("- DeepSeek API服务器响应慢")
                print("\n您可以尝试简化您的请求或稍后再试。\n")
            except Exception as e:
                print(f"\n❌ 处理请求时出错: {e}\n")
            
            print("\n--------------------")
            print("请输入新的指令，或输入 'exit' 退出")
            print("--------------------\n")
        except KeyboardInterrupt:
            logger.warning("检测到中断，正在退出...")
            break


if __name__ == "__main__":
    asyncio.run(main())