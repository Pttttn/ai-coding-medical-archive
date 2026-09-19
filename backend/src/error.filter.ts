import {ArgumentsHost,Catch,ExceptionFilter,HttpException} from '@nestjs/common';
import {Response} from 'express';
@Catch()
export class SafeErrorFilter implements ExceptionFilter {
  catch(error:unknown,host:ArgumentsHost) {
    const response=host.switchToHttp().getResponse<Response>();
    if(error instanceof HttpException) {
      const data=error.getResponse();
      const body=typeof data==='string'?{message:data}:data;
      response.status(error.getStatus()).json({...body as object,statusCode:error.getStatus()});return;
    }
    if((error as any)?.driverError?.code==='23505') {
      response.status(409).json({statusCode:409,code:'DUPLICATE',message:'Такая запись уже существует. Проверьте архив и корзину.'});return;
    }
    response.status(500).json({statusCode:500,code:'INTERNAL_ERROR',message:'Не удалось выполнить операцию. Повторите попытку.'});
  }
}
