import {DataSource} from 'typeorm';
import {ENTITIES} from './entities';
import {Initial1750000000000} from './migrations/Initial1750000000000';
export function createDataSource(url=process.env.DATABASE_URL) {
  if(!url)throw new Error('DATABASE_URL is required');
  return new DataSource({type:'postgres',url,entities:ENTITIES,migrations:[Initial1750000000000],migrationsRun:true,synchronize:false,logging:false,extra:{max:10}});
}
