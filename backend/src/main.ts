import 'reflect-metadata';
import {NestFactory} from '@nestjs/core';
import {ValidationPipe} from '@nestjs/common';
import {DocumentBuilder,SwaggerModule} from '@nestjs/swagger';
import helmet from 'helmet';
import {json} from 'express';
import {AppModule} from './app.module';
import {SafeErrorFilter} from './error.filter';

async function bootstrap(){
  const app=await NestFactory.create(AppModule,{logger:['warn'],bodyParser:false});
  app.use(json({limit:'1mb'}));
  app.use(helmet({contentSecurityPolicy:{directives:{defaultSrc:["'self'"],scriptSrc:["'self'","'unsafe-inline'"],styleSrc:["'self'","'unsafe-inline'"],imgSrc:["'self'","data:"],connectSrc:["'self'"]}},crossOriginEmbedderPolicy:false}));
  app.use((req:any,res:any,next:any)=>{res.setHeader('Cache-Control','no-store');next();});
  app.setGlobalPrefix('api');
  app.useGlobalPipes(new ValidationPipe({transform:true,whitelist:true,forbidNonWhitelisted:true}));
  app.useGlobalFilters(new SafeErrorFilter());
  const schema=new DocumentBuilder().setTitle('Local Medical Archive').setDescription('Local-only synthetic demo / personal archive. No authentication: publish on loopback only. All AI inference stays local.').setVersion('1.0.0').build();
  SwaggerModule.setup('docs',app,SwaggerModule.createDocument(app,schema),{swaggerOptions:{persistAuthorization:false,validatorUrl:null},customSiteTitle:'Local Archive API'});
  app.enableShutdownHooks();
  await app.listen(Number(process.env.PORT??3000),'0.0.0.0');
}
bootstrap().catch(()=>{process.stderr.write('Backend startup failed; check database and local configuration.\n');process.exit(1);});
