import {Module} from '@nestjs/common';
import {DataSource} from 'typeorm';
import {AppController} from './app.controller';
import {ArchiveService} from './archive.service';
import {ConsultationService} from './consultation.service';
import {ProcessingService} from './processing.service';
import {PurgeService} from './purge.service';
import {SeedService} from './seed.service';
import {AiClient} from './core';
import {createDataSource} from './database';
@Module({
  controllers:[AppController],
  providers:[
    {provide:DataSource,useFactory:async()=>{const source=createDataSource();await source.initialize();return source;}},
    AiClient,ArchiveService,ConsultationService,ProcessingService,PurgeService,SeedService,
  ],
})
export class AppModule {}
