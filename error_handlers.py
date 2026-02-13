import time
import logging
from functools import wraps
from typing import Callable, Any, TypeVar, Union, Optional

T = TypeVar('T')

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, 
                     exceptions: tuple = (Exception,), 
                     logger: Optional[logging.Logger] = None):
    """重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍数
        exceptions: 需要捕获的异常类型
        logger: 日志记录器
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        if logger:
                            logger.error(f"函数 {func.__name__} 在 {max_retries} 次重试后仍然失败: {e}")
                        raise e
                    
                    if logger:
                        logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{current_delay}秒后重试...")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # 理论上不会执行到这里，但为了满足类型检查器
            raise Exception("未知错误")
        
        return wrapper
    return decorator

def handle_errors(logger: Optional[logging.Logger] = None, 
                  default_return: Any = None, 
                  exceptions: tuple = (Exception,)):
    """错误处理装饰器
    
    Args:
        logger: 日志记录器
        default_return: 发生异常时的默认返回值
        exceptions: 需要捕获的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, Any]]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if logger:
                    logger.error(f"函数 {func.__name__} 发生错误: {e}")
                return default_return
        
        return wrapper
    return decorator

class ErrorHandler:
    """错误处理类"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("VideoSummary")
    
    def handle_request_error(self, error: Exception, operation: str) -> bool:
        """处理请求错误
        
        Args:
            error: 异常对象
            operation: 操作描述
            
        Returns:
            bool: 是否应该重试
        """
        if isinstance(error, ConnectionError):
            self.logger.warning(f"{operation} 连接错误: {error}")
            return True
        
        if isinstance(error, TimeoutError):
            self.logger.warning(f"{operation} 超时错误: {error}")
            return True
        
        self.logger.error(f"{operation} 不可恢复的错误: {error}")
        return False
    
    def log_api_response(self, response_data: dict, operation: str) -> bool:
        """记录API响应并检查是否成功
        
        Args:
            response_data: API响应数据
            operation: 操作描述
            
        Returns:
            bool: 响应是否成功
        """
        if not response_data:
            self.logger.error(f"{operation}: 收到空响应")
            return False
        
        if response_data.get("code") != 0:
            error_msg = response_data.get("message", "未知错误")
            self.logger.error(f"{operation} API错误: {error_msg}")
            return False
        
        self.logger.debug(f"{operation} API调用成功")
        return True

def safe_file_operation(logger: Optional[logging.Logger] = None):
    """文件操作安全装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except PermissionError as e:
                if logger:
                    logger.error(f"文件权限错误: {e}")
                raise
            except FileNotFoundError as e:
                if logger:
                    logger.error(f"文件未找到: {e}")
                raise
            except IOError as e:
                if logger:
                    logger.error(f"文件IO错误: {e}")
                raise
        
        return wrapper
    return decorator

class ValidationError(Exception):
    """自定义验证错误"""
    pass

def validate_video_id(video_id: str) -> bool:
    """验证视频ID格式"""
    if not video_id:
        raise ValidationError("视频ID不能为空")
    
    if video_id.startswith("BV"):
        if len(video_id) != 12:
            raise ValidationError(f"BV号长度不正确: {video_id}")
    elif video_id.startswith("av"):
        try:
            int(video_id[2:])
        except ValueError:
            raise ValidationError(f"AV号格式不正确: {video_id}")
    else:
        raise ValidationError(f"未知的视频ID格式: {video_id}")
    
    return True

def validate_url(url: str) -> bool:
    """验证URL格式"""
    if not url:
        raise ValidationError("URL不能为空")
    
    if not url.startswith(("http://", "https://")):
        raise ValidationError("URL必须以http://或https://开头")
    
    return True