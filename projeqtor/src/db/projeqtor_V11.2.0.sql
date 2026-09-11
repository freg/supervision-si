-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.2.0                                      //
-- // Date : 2024-01-05                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}filter` 
ADD COLUMN `idLayout` int(12) unsigned COMMENT '12';

INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle` ,`fonctionName`) VALUES
('0 1 * * *', '../tool/cronExecutionStandard.php', 1, 'cronRunConsistencyCheck');

-- Fix id for navigation
UPDATE `${prefix}navigation` SET id=100012001 WHERE name='menuImportProject';
UPDATE `${prefix}navigation` SET id=378 WHERE name='menuCriticalResources' and id>378; 
UPDATE `${prefix}navigation` SET id=379 WHERE name='menuResourceMaterial' and id>379; 
UPDATE `${prefix}navigation` SET id=380 WHERE name='menuAssignment' and id>380; 
UPDATE `${prefix}navigation` SET id=381 WHERE name='menuActivityExpense' and id>381; 
UPDATE `${prefix}navigation` SET id=382 WHERE name='menuActivityExpenseType' and id>382; 
UPDATE `${prefix}navigation` SET id=383 WHERE name='menuLessonLearned'  and id>383; 
UPDATE `${prefix}navigation` SET id=384 WHERE name='menuLessonLearnedType' and id>384; 
UPDATE `${prefix}navigation` SET id=385 WHERE name='menuAssumption' and id>385; 
UPDATE `${prefix}navigation` SET id=386 WHERE name='menuAssumptionType' and id>386; 
UPDATE `${prefix}navigation` SET id=387 WHERE name='menuConstraint' and id>387; 
UPDATE `${prefix}navigation` SET id=388 WHERE name='menuConstraintType' and id>388; 
UPDATE `${prefix}navigation` SET id=389 WHERE name='navProjectAnalysis' and id>389; 
UPDATE `${prefix}navigation` SET id=390 WHERE name='menuAction' and id>390; 

ALTER TABLE `${prefix}criticalresourcescenariopool` 	
ADD COLUMN `givenDate` date DEFAULT NULL;

UPDATE `${prefix}report` SET idle=1 WHERE name='reportPlanGantt';
UPDATE `${prefix}report` SET idle=1 WHERE name='reportPortfolioGantt';

UPDATE `${prefix}favorite` SET idle=1 WHERE idReport=49;
UPDATE `${prefix}favorite` SET idle=1 WHERE idReport=7;

UPDATE `${prefix}today` SET idle=1 WHERE idReport=49;
UPDATE `${prefix}today` SET idle=1 WHERE idReport=7;

UPDATE `${prefix}report` SET idReportCategory=0 WHERE name='reportPlanGantt';
UPDATE `${prefix}report` SET idReportCategory=0 WHERE name='reportPortfolioGantt';

CREATE TABLE `${prefix}waitingupdate` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`idUser` int(12) unsigned COMMENT '12',
`scope` varchar(100) DEFAULT NULL,
`itemId` int(12) unsigned COMMENT '12',
`parameter` varchar(100) DEFAULT NULL,
`storeDateTime` datetime,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}activity` ADD `tags` VARCHAR(1000) DEFAULT NULL;
ALTER TABLE `${prefix}project` ADD `tags` VARCHAR(1000) DEFAULT NULL;
ALTER TABLE `${prefix}ticket` ADD `tags` VARCHAR(1000) DEFAULT NULL;

ALTER TABLE `${prefix}worktokenclientcontract` 
ADD COLUMN `idleToken` int(1)  unsigned DEFAULT '0' COMMENT '1';

INSERT INTO `${prefix}habilitationother` (idProfile, rightAccess, scope) VALUES
(1,1,'canCreateTags'),
(3,1,'canCreateTags');

ALTER TABLE `${prefix}tag` DROP INDEX tagName;
CREATE UNIQUE INDEX tagName ON `${prefix}tag` (`refType`,`name`);