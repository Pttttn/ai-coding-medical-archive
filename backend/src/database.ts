import {ConsultationHistory1752000000000} from './migrations/ConsultationHistory1752000000000';
import {DataSource} from 'typeorm';
import {ProcessingStages1753000000000} from './migrations/ProcessingStages1753000000000';
import {ProcessingRevisions1754000000000} from './migrations/ProcessingRevisions1754000000000';
import {SourceIR1751000000000} from './migrations/SourceIR1751000000000';
import {ENTITIES} from './entities';
import {Initial1750000000000} from './migrations/Initial1750000000000';
export function createDataSource(url=process.env.DATABASE_URL) {
  if(!url)throw new Error('DATABASE_URL is required');
  return new DataSource({type:'postgres',url,entities:ENTITIES,migrations:[Initial1750000000000,SourceIR1751000000000,ConsultationHistory1752000000000,ProcessingStages1753000000000,ProcessingRevisions1754000000000],migrationsRun:true,synchronize:false,logging:false,extra:{max:10}});
}
