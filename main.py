
import json
import time
import argparse
import os
import logging

from concurrent.futures import ThreadPoolExecutor
from utils import reserve, get_user_credentials


SLEEPTIME        = 0.5      # 每个用户每次抢座的间隔
ENABLE_SLIDER    = False    # 是否有滑块验证
MAX_ATTEMPT      = 30       # 每个用户最大尝试次数
RESERVE_NEXT_DAY = True     # 预约明天而不是今天的


# 配置日志的基本设置，设置日志级别为INFO，并定义日志的格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义一个lambda函数，用于获取当前时间，如果action为True，则获取的是UTC+8时区的时间，否则获取本地时间
get_current_time = lambda action: time.strftime("%H:%M:%S", time.localtime(time.time() + 8*3600)) if action else time.strftime("%H:%M:%S", time.localtime(time.time()))
# 定义一个lambda函数，用于获取当前是星期几，如果action为True，则获取的是UTC+8时区的时间对应的星期，否则获取本地时间对应的星期
get_current_dayofweek = lambda action: time.strftime("%A", time.localtime(time.time() + 8*3600)) if action else time.strftime("%A", time.localtime(time.time()))

def login_and_reserve_single_user(user, username, password, action):
    # 这里是单个用户登录并尝试预约的逻辑
    # 解包用户信息，包括用户名、密码、预约时间、房间ID、座位ID和预约星期
    username, password, times, roomid, seatid, daysofweek = user.values()
    # 如果启用了action模式，则使用传入的用户名和密码
    if action:
        username, password = username, password
    # 如果当前星期不在用户设置的预约星期中，则跳过
    current_dayofweek = get_current_dayofweek(action)
    if (current_dayofweek not in daysofweek):
        logging.error(f"[Time] -User {username} Today not set to reserve")
        return False
    # 尝试预约
    logging.info(f"[Try] - {username} -- {times} -- {roomid} -- {seatid} ---- ")
    s = reserve(sleep_time=SLEEPTIME, max_attempt=MAX_ATTEMPT, enable_slider=ENABLE_SLIDER,
                reserve_next_day=RESERVE_NEXT_DAY)
    s.get_login_status()
    s.login(username, password)
    s.requests.headers.update({'Host': 'office.chaoxing.com'})
    suc = s.submit(times, roomid, seatid, action,username)
    return suc


def main_parallel(users, action=False):
    # 获取用户凭据，如果启用action模式
    usernames, passwords = None, None
    if action:
        usernames, passwords = get_user_credentials(action)

    # 使用ThreadPoolExecutor来并行化登录和预约过程
    with ThreadPoolExecutor(max_workers=len(users)) as executor:
        # 准备任务列表
        futures = []
        for index, user in enumerate(users):
            # 将每个用户的登录和预约作为一个任务提交到线程池
            futures.append(
                executor.submit(login_and_reserve_single_user, user, usernames.split(',')[index] if action else None,
                                passwords.split(',')[index] if action else None, action))

        # 等待所有任务完成，并收集结果
        success_list = [future.result() for future in futures]

    # 打印成功列表
    print(f"Success list: {success_list}")

# 当此脚本被直接运行时，以下代码块将被执行
if __name__ == "__main__":
    # 获取当前脚本的绝对路径，并构造配置文件的路径
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    # 创建一个 ArgumentParser 对象，用于处理命令行参数
    parser = argparse.ArgumentParser(prog='Chao Xing seat auto reserve')
    # 添加命令行参数选项
    # '-u' 或 '--user' 选项，用于指定用户配置文件，默认为 config.json
    parser.add_argument('-u', '--user', default=config_path, help='user config file')
    # '-m' 或 '--method' 选项，用于指定执行方法，默认为 "reserve"，可选值为 "reserve", "debug", "room"
    parser.add_argument('-m', '--method', default="reserve", choices=["reserve"], help='for debug')
    # '-a' 或 '--action' 选项，如果使用此选项，将设置 action 为 True，用于在 GitHub Actions 中启用
    parser.add_argument('-a', '--action', action="store_true", help='use --action to enable in github action')
    # 解析命令行参数
    args = parser.parse_args()
    # 定义一个函数字典，将方法名映射到对应的函数
    func_dict = {"reserve": main_parallel}  # 使用并行化的main函数
    # func_dict = {"reserve": main}

    # 打开用户配置文件，读取配置信息
    with open(args.user, "r+") as data:
        usersdata = json.load(data)["reserve"]
    # 根据命令行参数指定的方法，调用相应的函数，并传入用户配置数据和 action 标志
    func_dict[args.method](usersdata, args.action)



